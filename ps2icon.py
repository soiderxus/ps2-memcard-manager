#
# ps2icon.py
#
# Part of the Python 3 port of mymc.  Public Domain.
#

"""Parse and render PS2 3D save icons (the *.ico files named in icon.sys).

The Windows build of mymc used a Direct3D DLL (mymcicon) for this.  This
module is a portable replacement: it decodes the icon model, animation
and texture, and renders it with a small software rasterizer written
with numpy, producing an RGB image that any toolkit can display.

Icon file layout (little endian):
	header:   u32 magic (0x010000), u32 shape count, u32 texture type,
		  f32 unknown, u32 vertex count
	vertices: per vertex: shape count * (s16 x, y, z, w),
		  s16 normal x, y, z, w,  s16 u, v,  u8 r, g, b, a
		  (coordinates are fixed point, 1.0 == 4096)
	animation: u32 magic (1), u32 frame length, f32 speed,
		  u32 play offset, u32 frame count, then per frame:
		  u32 shape, u32 key count, key count * (f32 time, f32 value)
	texture:  128x128 16-bit A1B5G5R5 pixels, uncompressed or (when
		  bit 3 of the texture type is set) run length encoded
"""

import math
import struct

import numpy as np

ICON_MAGIC = 0x010000
TEX_SIZE = 128
LIGHT_SIGN = 1.0

class icon_error(Exception):
	pass

def _decode_texture_rle(data, off):
	(size,) = struct.unpack_from("<I", data, off)
	off += 4
	end = min(off + size, len(data))
	out = []
	need = TEX_SIZE * TEX_SIZE
	count = 0
	while off + 2 <= end and count < need:
		(code,) = struct.unpack_from("<H", data, off)
		off += 2
		if code & 0x8000:
			n = 0x10000 - code
			chunk = data[off : off + n * 2]
			off += n * 2
			out.append(chunk)
			count += len(chunk) // 2
		else:
			out.append(data[off : off + 2] * code)
			off += 2
			count += code
	raw = b"".join(out)[: need * 2]
	raw += b"\0" * (need * 2 - len(raw))
	return raw

def _texture_to_rgb(raw):
	px = np.frombuffer(raw, dtype="<u2", count=TEX_SIZE * TEX_SIZE)
	px = px.reshape(TEX_SIZE, TEX_SIZE)
	r = (px & 0x1F).astype(np.float32)
	g = ((px >> 5) & 0x1F).astype(np.float32)
	b = ((px >> 10) & 0x1F).astype(np.float32)
	return np.stack([r, g, b], axis=-1) * (1.0 / 31.0)

class ps2_icon(object):
	"""A decoded PS2 3D icon."""

	def __init__(self, data):
		data = bytes(data)
		if len(data) < 20:
			raise icon_error("icon file too short")
		(magic, nshapes, tex_type, _unk, nverts) \
			= struct.unpack_from("<IIIfI", data, 0)
		if magic != ICON_MAGIC or nshapes < 1 or nverts % 3 != 0:
			raise icon_error("not a PS2 icon")
		self.tex_type = tex_type

		# vertex block, parsed with a structured numpy dtype
		vdtype = np.dtype([("pos", "<i2", (nshapes, 4)),
				   ("normal", "<i2", (4,)),
				   ("uv", "<i2", (2,)),
				   ("color", "u1", (4,))])
		off = 20
		vsize = vdtype.itemsize * nverts
		if off + vsize > len(data):
			raise icon_error("truncated vertex data")
		v = np.frombuffer(data, dtype=vdtype, count=nverts, offset=off)
		off += vsize
		scale = 1.0 / 4096
		# shapes: (nshapes, nverts, 3)
		self.shapes = (v["pos"][:, :, :3].astype(np.float32) * scale) \
			.transpose(1, 0, 2).copy()
		self.normals = v["normal"][:, :3].astype(np.float32) * scale
		self.uvs = v["uv"].astype(np.float32) * scale
		self.colors = v["color"][:, :3].astype(np.float32) / 128.0
		self.colors = np.minimum(self.colors, 1.0)

		# animation
		self.frame_length = 1
		self.anim_speed = 1.0
		self.frames = []
		if off + 20 <= len(data):
			(amagic, flen, speed, _play, nframes) \
				= struct.unpack_from("<IIfII", data, off)
			off += 20
			self.frame_length = max(flen, 1)
			if speed > 0 and math.isfinite(speed):
				self.anim_speed = speed
			for i in range(nframes):
				(shape, nkeys) = struct.unpack_from("<II", data, off)
				off += 8
				keys = struct.unpack_from("<%df" % (nkeys * 2),
							  data, off)
				off += nkeys * 8
				self.frames.append((shape,
						    list(zip(keys[0::2], keys[1::2]))))

		# texture
		if tex_type & 0x08:
			raw = _decode_texture_rle(data, off)
		else:
			raw = data[off : off + TEX_SIZE * TEX_SIZE * 2]
			raw += b"\0" * (TEX_SIZE * TEX_SIZE * 2 - len(raw))
		if tex_type & 0x04 or tex_type & 0x08 or len(raw):
			self.texture = _texture_to_rgb(raw)
		else:
			self.texture = None

		# bounding sphere over all shapes, for automatic framing
		allpos = self.shapes.reshape(-1, 3)
		lo = allpos.min(axis=0)
		hi = allpos.max(axis=0)
		self.center = (lo + hi) / 2
		self.radius = max(float(np.linalg.norm(hi - lo)) / 2, 1e-3)

	def shape_at(self, t):
		"""Vertex positions at animation time t (in frames)."""

		nshapes = len(self.shapes)
		if nshapes == 1:
			return self.shapes[0]
		t = t % self.frame_length
		weights = np.zeros(nshapes, dtype=np.float32)
		for (shape, keys) in self.frames:
			if shape >= nshapes or not keys:
				continue
			weights[shape] += _interp_keys(keys, t)
		total = float(weights.sum())
		if total <= 1e-6:
			# no usable key data: cycle through the shapes
			f = t / self.frame_length * nshapes
			i = int(f) % nshapes
			j = (i + 1) % nshapes
			a = f - int(f)
			return self.shapes[i] * (1 - a) + self.shapes[j] * a
		weights /= total
		return np.tensordot(weights, self.shapes, axes=1)

def _interp_keys(keys, t):
	if t <= keys[0][0]:
		return keys[0][1]
	for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
		if t <= t1:
			if t1 <= t0:
				return v1
			return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
	return keys[-1][1]

class icon_sys_info(object):
	"""Display settings (background, lights) taken from icon.sys."""

	def __init__(self, s):
		self.bg_corners = [(0.1, 0.1, 0.3)] * 4
		self.light_dirs = []
		self.light_colours = []
		self.ambient = (0.5, 0.5, 0.5)
		if s is None or len(s) < 964:
			return
		bg = struct.unpack_from("<16I", s, 0x10)
		self.bg_corners = [tuple(min(c / 128.0, 1.0)
					 for c in bg[i * 4 : i * 4 + 3])
				   for i in range(4)]
		dirs = struct.unpack_from("<12f", s, 0x50)
		cols = struct.unpack_from("<12f", s, 0x80)
		amb = struct.unpack_from("<4f", s, 0xB0)
		self.light_dirs = [dirs[i * 4 : i * 4 + 3] for i in range(3)]
		self.light_colours = [cols[i * 4 : i * 4 + 3] for i in range(3)]
		self.ambient = amb[:3]

def _normalize(v):
	v = np.asarray(v, dtype=np.float32)
	n = float(np.linalg.norm(v))
	if n < 1e-9:
		return v
	return v / n

def _gradient(w, h, corners):
	# corners: top-left, top-right, bottom-left, bottom-right
	c = np.array(corners, dtype=np.float32)
	y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
	x = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
	top = c[0] * (1 - x) + c[1] * x
	bottom = c[2] * (1 - x) + c[3] * x
	return top * (1 - y) + bottom * y

def render(icon, width, height, t = 0.0, yaw = 0.0, info = None,
	   lighting = None, camera = (0, 4, -8)):
	"""Render the icon to an (height, width, 3) uint8 RGB array.

	lighting is a dict like the lighting_* dicts in gui.py, or None
	to use the lights from icon.sys (info)."""

	if info is None:
		info = icon_sys_info(None)
	img = _gradient(width, height, info.bg_corners)

	pos = icon.shape_at(t) - icon.center
	normals = icon.normals

	# PS2 icons use a y-down coordinate system; flip to y-up
	flip = np.array([1, -1, 1], dtype=np.float32)
	pos = pos * flip
	normals = normals * flip

	# spin around the vertical axis
	c, s = math.cos(yaw), math.sin(yaw)
	rot = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float32)
	pos = pos @ rot.T
	normals = normals @ rot.T

	# per-vertex lighting
	use_lighting = True
	vertex_diffuse = True
	if lighting is None:
		dirs, cols, amb = info.light_dirs, info.light_colours, \
				  info.ambient
	else:
		use_lighting = lighting["lighting"]
		vertex_diffuse = lighting["vertex_diffuse"]
		if lighting["alt_lighting"]:
			dirs = [d[:3] for d in lighting["light_dirs"]]
			cols = [d[:3] for d in lighting["light_colours"]]
			amb = lighting["ambient"][:3]
		else:
			dirs, cols, amb = info.light_dirs, \
					  info.light_colours, info.ambient
	nverts = len(pos)
	if vertex_diffuse:
		shade = icon.colors.copy()
	else:
		shade = np.ones((nverts, 3), dtype=np.float32)
	if use_lighting and dirs:
		nrm = normals / np.maximum(
			np.linalg.norm(normals, axis=1, keepdims=True), 1e-6)
		light = np.tile(np.asarray(amb, dtype=np.float32), (nverts, 1))
		for d, col in zip(dirs, cols):
			# lights stay fixed while the model spins
			L = _normalize(np.array(d, dtype=np.float32) * flip)
			lam = np.maximum(nrm @ L * LIGHT_SIGN, 0)
			light += lam[:, None] * np.asarray(col, dtype=np.float32)
		shade = shade * np.clip(light, 0, 1.5)

	# camera: keep its direction, but distance it to fit the icon
	cam = _normalize(np.array(camera, dtype=np.float32))
	dist = float(np.linalg.norm(camera))
	fov_scale = 1.0 / math.tan(math.radians(30) / 2)
	fit_dist = icon.radius * fov_scale * 1.15
	eye = cam * max(fit_dist, icon.radius * 1.5) * (dist / 8.0)
	eye = eye * flip
	fwd = _normalize(-eye)
	right = _normalize(np.cross(np.array([0, 1, 0], np.float32), fwd))
	up = np.cross(fwd, right)
	rel = pos - eye
	vx = rel @ right
	vy = rel @ up
	vz = rel @ fwd
	vz = np.maximum(vz, 1e-3)
	f = fov_scale * min(width, height) / 2
	sx = width / 2 + vx / vz * f
	sy = height / 2 - vy / vz * f

	zbuf = np.full((height, width), np.inf, dtype=np.float32)
	tex = icon.texture
	uvs = icon.uvs

	for k in range(0, nverts - 2, 3):
		x0, x1, x2 = sx[k], sx[k + 1], sx[k + 2]
		y0, y1, y2 = sy[k], sy[k + 1], sy[k + 2]
		area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
		if abs(area) < 1e-9:
			continue
		minx = max(int(math.floor(min(x0, x1, x2))), 0)
		maxx = min(int(math.ceil(max(x0, x1, x2))), width - 1)
		miny = max(int(math.floor(min(y0, y1, y2))), 0)
		maxy = min(int(math.ceil(max(y0, y1, y2))), height - 1)
		if minx > maxx or miny > maxy:
			continue
		px = np.arange(minx, maxx + 1, dtype=np.float32) + 0.5
		py = np.arange(miny, maxy + 1, dtype=np.float32)[:, None] + 0.5
		w0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / area
		w1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / area
		w2 = 1 - w0 - w1
		inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
		if not inside.any():
			continue
		# perspective correct interpolation
		iz0, iz1, iz2 = 1 / vz[k], 1 / vz[k + 1], 1 / vz[k + 2]
		iz = w0 * iz0 + w1 * iz1 + w2 * iz2
		z = 1 / iz
		zb = zbuf[miny : maxy + 1, minx : maxx + 1]
		mask = inside & (z < zb)
		if not mask.any():
			continue
		zb[mask] = z[mask]
		p0 = w0 * iz0 * z
		p1 = w1 * iz1 * z
		p2 = w2 * iz2 * z
		p0, p1, p2 = p0[mask], p1[mask], p2[mask]
		col = (p0[:, None] * shade[k] + p1[:, None] * shade[k + 1]
		       + p2[:, None] * shade[k + 2])
		if tex is not None:
			u = p0 * uvs[k, 0] + p1 * uvs[k + 1, 0] \
			    + p2 * uvs[k + 2, 0]
			v = p0 * uvs[k, 1] + p1 * uvs[k + 1, 1] \
			    + p2 * uvs[k + 2, 1]
			tu = (u * TEX_SIZE).astype(np.int32) % TEX_SIZE
			tv = (v * TEX_SIZE).astype(np.int32) % TEX_SIZE
			col = col * tex[tv, tu]
		region = img[miny : maxy + 1, minx : maxx + 1]
		region[mask] = col

	return (np.clip(img, 0, 1) * 255).astype(np.uint8)
