# mymc (versión para Python 3)

*[Read in English](README.md)*

Herramienta para gestionar **imágenes de tarjetas de memoria de PlayStation 2**
como las que usa el emulador PCSX2 (`Mcd001.ps2`). Importa y exporta
partidas guardadas, y también crea, inspecciona y verifica imágenes de
tarjeta.

Es un port de **mymc 2.7**, de Ross Ridge, de Python 2 a **Python 3**,
con la interfaz gráfica funcionando sobre wxPython 4 y un visor nuevo de
iconos 3D multiplataforma.

## Características

- **Interfaz gráfica**: abre una tarjeta, muestra sus partidas (con los
  títulos en japonés), importa, exporta y borra partidas, y muestra el
  **icono 3D** animado de cada una.
- **Línea de comandos**: todas las operaciones, más algunas avanzadas
  (añadir y extraer archivos sueltos, crear directorios, renombrar,
  cambiar atributos, verificar el sistema de archivos, formatear
  tarjetas nuevas).
- **Formatos de partida**

  | Formato | Extensión | Importar | Exportar |
  |---|---|:---:|:---:|
  | EMS / uLaunchELF | `.psu` | ✅ | ✅ |
  | MAX Drive | `.max` | ✅ | ✅ |
  | CodeBreaker | `.cbs` | ✅ | — |
  | SharkPort / X-Port | `.sps` `.xps` | ✅ | — |

- Imágenes con o sin datos ECC. Los errores de un bit se corrigen solos.

## Requisitos

| Componente | Sirve para | ¿Obligatorio? |
|---|---|---|
| **Python 3.8+** | todo | sí |
| **wxPython 4.x** | la interfaz gráfica | solo para la GUI |
| **numpy** | los iconos 3D en la GUI | opcional |

La herramienta de línea de comandos funciona con Python solo, sin
paquetes extra. Sin wxPython solo queda la línea de comandos. Sin numpy
la GUI funciona igual, pero no muestra los iconos.

> Probado con Python 3.14, wxPython 4.2.4 (GTK3) y numpy 2.x en Fedora 44.

## Instalación

### 1. Instalar las dependencias

Usa los paquetes de tu distribución. Es lo más fácil, porque wxPython no
publica paquetes precompilados para Linux en PyPI. Los nombres de los
paquetes pueden variar un poco entre versiones de cada distribución.

**Fedora / RHEL / CentOS Stream / AlmaLinux / Rocky** (en los clones de RHEL puede hacer falta EPEL)
```sh
sudo dnf install python3 python3-wxpython4 python3-numpy
```

**Debian / Ubuntu / Linux Mint / Pop!_OS**
```sh
sudo apt install python3 python3-wxgtk4.0 python3-numpy
```

**Arch Linux / Manjaro / EndeavourOS**
```sh
sudo pacman -S python python-wxpython python-numpy
```

**openSUSE Tumbleweed / Leap**
```sh
sudo zypper install python3 python3-wxPython python3-numpy
```

**Gentoo**
```sh
sudo emerge --ask dev-python/wxpython dev-python/numpy
```

**Void Linux**
```sh
sudo xbps-install python3 python3-wxPython python3-numpy
```

**Alpine Linux**
```sh
sudo apk add python3 py3-wxpython py3-numpy
```

**NixOS / Nix** (shell temporal)
```sh
nix-shell -p "python3.withPackages (ps: [ ps.wxpython ps.numpy ])"
```

**Cualquier distribución con pip (entorno virtual)**

En Linux, `pip install wxPython` compila desde el código fuente. Tarda
bastante y necesita un compilador de C++ y los archivos de desarrollo de
GTK3. Hay paquetes precompilados para las distribuciones más comunes en
<https://extras.wxpython.org/wxPython4/extras/linux/>.
```sh
python3 -m venv venv
. venv/bin/activate
# Ejemplo con un paquete precompilado (elige la carpeta de tu distro):
pip install -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04 wxPython
pip install numpy
```

**Windows / macOS** (no probado con este port)
```sh
pip install wxPython numpy
```

### 2. Descargar mymc

```sh
git clone https://github.com/soiderxus/my-mc-gui-native-for-linux.git
cd my-mc-gui-native-for-linux
chmod +x mymc.py mymc-gui
```

No hace falta compilar nada. Mantén todos los archivos `.py` juntos en
la misma carpeta.

### Comprobar la instalación

```sh
python3 -c "import wx; print('wxPython', wx.version())"
python3 -c "import numpy; print('numpy', numpy.__version__)"
./mymc.py --version
```

## Uso

### Interfaz gráfica

```sh
./mymc-gui                    # pregunta qué tarjeta abrir
./mymc-gui ~/.config/PCSX2/memcards/Mcd001.ps2
```
Ejecutar `./mymc.py` sin argumentos también abre la GUI.

- **Open**: elige una imagen de tarjeta `.ps2`.
- **Import**: añade una o varias partidas (`.psu .max .cbs .sps .xps`).
- **Export**: selecciona partidas y expórtalas como `.psu` o `.max`.
- **File → Delete**: borra las partidas seleccionadas.
- Al seleccionar una partida se ve su icono 3D. **Haz clic derecho sobre
  el icono** (o usa *Options → Icon Window*) para cambiar la animación,
  la iluminación y la cámara.
- *Options → ASCII Descriptions* muestra los títulos en ASCII simple.

> ⚠️ **No modifiques una tarjeta mientras PCSX2 está abierto.** Cierra
> antes el emulador o la tarjeta puede corromperse. Haz copia de
> seguridad de tus tarjetas antes de usar cualquier herramienta sobre
> ellas.

### Línea de comandos

```
./mymc.py [-i] tarjeta.ps2 comando [opciones] [argumentos]
```

| Comando | Descripción |
|---|---|
| `dir` | Lista las partidas con su título y tamaño, y el espacio libre |
| `ls [dir]` | Lista los archivos de un directorio |
| `import partida...` | Importa partidas |
| `export [-m\|-p] [-l] dir...` | Exporta partidas (`-p` .psu, por defecto; `-m` .max; `-l` nombres largos descriptivos) |
| `delete dir...` | Borra una partida (con todo su contenido) |
| `add`, `extract`, `mkdir`, `remove`, `rename` | Trabajan con archivos sueltos |
| `set`, `clear` | Cambian atributos (protegido, oculto, …) |
| `check` | Busca errores en el sistema de archivos |
| `df` | Muestra el espacio libre |
| `format [-e] [-c clusters]` | Crea una tarjeta nueva (`-e`: sin ECC) |
| `gui` | Abre la GUI con esta tarjeta |

Ejecuta `./mymc.py --help` o `./mymc.py tarjeta.ps2 COMANDO --help` para
ver los detalles.

Ejemplos:
```sh
./mymc.py Mcd001.ps2 dir
./mymc.py Mcd001.ps2 import "Algun Juego.psu"
./mymc.py Mcd001.ps2 export -l BASLUS-12345GAME
./mymc.py nueva.ps2 format
```

## Opcional: acceso en el menú (Linux)

Para que mymc aparezca en el menú de aplicaciones del escritorio, crea
`~/.local/share/applications/mymc.desktop` y cambia las rutas por la
carpeta donde clonaste el repositorio:
```ini
[Desktop Entry]
Type=Application
Name=mymc
Comment=Gestor de tarjetas de memoria de PS2
Exec=/ruta/a/mymc/mymc-gui %f
Terminal=false
Categories=Utility;Game;
```

## Cambios respecto a la 2.7 original

- Port a Python 3: los datos de la tarjeta se manejan como `bytes` y los
  nombres de archivo de la tarjeta se conservan sin pérdidas.
- GUI adaptada a wxPython 4 (Phoenix).
- **Nuevo `ps2icon.py`**: visor de iconos 3D multiplataforma
  (renderizado por software con numpy). Sustituye a la DLL de Direct3D,
  que solo funcionaba en Windows.
- Eliminadas las DLL nativas que solo existían para Windows (`mymcsup`,
  `mymcicon`). Siempre se usa el código en Python puro.
- Al exportar desde la GUI, la extensión `.psu` / `.max` ahora depende
  del tipo de archivo elegido.
- Bugs de la 2.7 corregidos:
  - `format -e` (sin ECC) creaba imágenes de tamaño incorrecto
  - `readline()` sobre archivos de la tarjeta devolvía una longitud incorrecta
  - `extract -o ARCHIVO` nunca cerraba el archivo de salida
  - `dir` fallaba con partidas de PlayStation/PocketStation
  - varias rutas de error usaban nombres que no existían

### Limitaciones conocidas

- Las partidas en formato CodeBreaker y SharkPort/X-Port se pueden
  importar pero no exportar (igual que en el original).
- El visor 3D se comprobó con iconos reales de una sola forma y textura
  sin comprimir. Los iconos que cambian de forma (animación con varias
  formas) o que usan textura comprimida están soportados, pero no había
  ejemplos reales para verificarlos.
- Las partidas de PS3 en formato `.PSV` no están soportadas.

## Créditos y licencia

- mymc original de **Ross Ridge**, publicado como **dominio público**.
  La documentación original está en [`README.txt`](README.txt).
- El port a Python 3, la GUI en wxPython 4 y el visor de iconos 3D
  también se publican como dominio público, bajo la [Unlicense](LICENSE).
