#
# filedialogs.py
#
# Part of the Python 3 port of mymc.  Public Domain.
#

"""File dialogs that use the desktop's own file chooser.

On Linux, wxPython always shows the GTK file dialog.  This module asks
the XDG desktop portal (org.freedesktop.portal.FileChooser, over D-Bus)
instead, so each desktop shows its native dialog: Dolphin's on KDE
Plasma, the GTK/Nautilus one on GNOME, and so on.

If the portal isn't available (no xdg-desktop-portal, no PyGObject,
Windows/macOS, or an error), the regular wx dialogs are used.  Set the
environment variable MYMC_PORTAL=0 to always use the wx dialogs.

filters are lists of (label, [glob patterns]) tuples, for example
[("Memory card images", ["*.ps2"]), ("All files", ["*"])].
"""

import itertools
import os
import sys

import wx

try:
	import gi
	gi.require_version("Gio", "2.0")
	from gi.repository import Gio, GLib
except Exception:
	Gio = GLib = None

_PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_FILE_CHOOSER = "org.freedesktop.portal.FileChooser"
_REQUEST = "org.freedesktop.portal.Request"

_tokens = itertools.count(1)
_portal_version = None		# None = not checked yet, 0 = unavailable


def _portal_available():
	global _portal_version
	if _portal_version is None:
		_portal_version = 0
		if (Gio is not None and sys.platform.startswith("linux")
		    and os.environ.get("MYMC_PORTAL", "1") != "0"):
			try:
				bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
				reply = bus.call_sync(
					_PORTAL_BUS_NAME, _PORTAL_PATH,
					"org.freedesktop.DBus.Properties", "Get",
					GLib.Variant("(ss)", (_FILE_CHOOSER, "version")),
					GLib.VariantType("(v)"),
					Gio.DBusCallFlags.NONE, 3000, None)
				_portal_version = int(reply.unpack()[0])
			except Exception:
				_portal_version = 0
	return _portal_version


def _parent_handle(parent):
	"""Window identifier so the dialog can be placed over our window.

	Only possible on X11; on Wayland it would need xdg-foreign, so the
	dialog is shown unparented there (our window is disabled meanwhile)."""
	on_wayland = (os.environ.get("WAYLAND_DISPLAY")
		      and os.environ.get("GDK_BACKEND", "") != "x11")
	if parent is None or on_wayland:
		return ""
	try:
		handle = parent.GetHandle()
		if handle:
			return "x11:%x" % handle
	except Exception:
		pass
	return ""


def _filters_variant(filters):
	return GLib.Variant("a(sa(us))",
			    [(label, [(0, p) for p in patterns])
			     for (label, patterns) in filters])


def _folder_variant(directory):
	return GLib.Variant("ay", os.fsencode(directory) + b"\0")


def _portal_request(parent, method, title, options):
	"""Show a portal dialog and wait for it.  Returns the results dict,
	{} if the user cancelled, or raises on failure."""

	bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
	token = "mymc%d_%d" % (os.getpid(), next(_tokens))
	sender = bus.get_unique_name()[1:].replace(".", "_")
	handle = "%s/request/%s/%s" % (_PORTAL_PATH, sender, token)
	options = dict(options)
	options["handle_token"] = GLib.Variant("s", token)

	outcome = {}
	loop = GLib.MainLoop()

	def on_response(conn, sender_name, path, iface, signal, params, *data):
		code, results = params.unpack()
		outcome["code"] = code
		outcome["results"] = results
		loop.quit()

	# Subscribe before calling, so the response can't be missed.
	sub = bus.signal_subscribe(_PORTAL_BUS_NAME, _REQUEST, "Response",
				   handle, None, Gio.DBusSignalFlags.NONE,
				   on_response)
	try:
		bus.call_sync(_PORTAL_BUS_NAME, _PORTAL_PATH, _FILE_CHOOSER,
			      method,
			      GLib.Variant("(ssa{sv})",
					   (_parent_handle(parent), title, options)),
			      GLib.VariantType("(o)"),
			      Gio.DBusCallFlags.NONE, -1, None)
		# Keep our windows from reacting while the dialog is open;
		# wx keeps repainting because GTK shares this main loop.
		disabler = wx.WindowDisabler()
		try:
			loop.run()
		finally:
			del disabler
	finally:
		bus.signal_unsubscribe(sub)

	code = outcome.get("code", 2)
	if code == 1:
		return {}		# cancelled
	if code != 0:
		raise RuntimeError("file chooser portal failed (%d)" % code)
	return outcome["results"]


def _uris_to_paths(results):
	paths = []
	for uri in results.get("uris", []):
		path = Gio.File.new_for_uri(uri).get_path()
		if path:
			paths.append(path)
	return paths


def _filter_index(results, filters):
	current = results.get("current_filter")
	if current:
		for i, (label, _) in enumerate(filters):
			if label == current[0]:
				return i
	return 0


def _wx_wildcard(filters):
	return "|".join("%s|%s" % (label, ";".join(patterns))
			for (label, patterns) in filters)


# --- public API -----------------------------------------------------------

def open_files(parent, title, directory = "", filters = (), multiple = False):
	"""Ask for existing file(s).  Returns a list of paths ([] = cancelled)."""

	filters = list(filters)
	if _portal_available():
		try:
			options = {"multiple": GLib.Variant("b", multiple)}
			if filters:
				options["filters"] = _filters_variant(filters)
				options["current_filter"] = GLib.Variant(
					"(sa(us))", (filters[0][0],
						     [(0, p) for p in filters[0][1]]))
			if directory and os.path.isdir(directory) \
			   and _portal_version >= 3:
				options["current_folder"] = _folder_variant(directory)
			return _uris_to_paths(_portal_request(parent, "OpenFile",
							      title, options))
		except Exception as e:
			print("file chooser portal unavailable, using wx:", e)

	style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
	if multiple:
		style |= wx.FD_MULTIPLE
	fd = wx.FileDialog(parent, title, directory,
			   wildcard = _wx_wildcard(filters) or "*", style = style)
	try:
		if fd.ShowModal() == wx.ID_CANCEL:
			return []
		return list(fd.GetPaths()) if multiple else [fd.GetPath()]
	finally:
		fd.Destroy()


def save_file(parent, title, directory = "", name = "", filters = ()):
	"""Ask where to save a file.  Returns (path, filter_index), or
	(None, None) if cancelled."""

	filters = list(filters)
	if _portal_available():
		try:
			options = {}
			if name:
				options["current_name"] = GLib.Variant("s", name)
			if directory and os.path.isdir(directory):
				options["current_folder"] = _folder_variant(directory)
			if filters:
				options["filters"] = _filters_variant(filters)
			results = _portal_request(parent, "SaveFile", title, options)
			paths = _uris_to_paths(results)
			if not paths:
				return (None, None)
			return (paths[0], _filter_index(results, filters))
		except Exception as e:
			print("file chooser portal unavailable, using wx:", e)

	fd = wx.FileDialog(parent, title, directory, name,
			   _wx_wildcard(filters) or "*",
			   wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
	try:
		if fd.ShowModal() == wx.ID_CANCEL:
			return (None, None)
		return (fd.GetPath(), fd.GetFilterIndex())
	finally:
		fd.Destroy()


def choose_directory(parent, title, directory = ""):
	"""Ask for a folder.  Returns its path, or None if cancelled."""

	if _portal_available() >= 3:
		try:
			options = {"directory": GLib.Variant("b", True)}
			if directory and os.path.isdir(directory):
				options["current_folder"] = _folder_variant(directory)
			paths = _uris_to_paths(_portal_request(parent, "OpenFile",
							       title, options))
			return paths[0] if paths else None
		except Exception as e:
			print("file chooser portal unavailable, using wx:", e)

	path = wx.DirSelector(title, directory, parent = parent)
	return path or None
