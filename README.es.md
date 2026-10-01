# msi-ultrapower

**Modos de energía para portátiles MSI en KDE Plasma.**

[English](README.md) · [Türkçe](README.tr.md) · [Русский](README.ru.md) · **Español** · [العربية](README.ar.md)

Con un clic cambia tu portátil MSI entre los modos de rendimiento, equilibrado y batería. Cada modo
ajusta a la vez el perfil de energía, la frecuencia de actualización y el brillo de la pantalla, el
ventilador y el modo del EC, el turbo de la CPU, la luz del teclado, el ahorro de energía de los
dispositivos y la GPU NVIDIA, y lo deshace todo si falla algún paso.

![Ventana Modos de energía](docs/screenshot.png)

## Instalación

En Arch, CachyOS, EndeavourOS o Manjaro con KDE Plasma 6:

```sh
curl -fsSL https://raw.githubusercontent.com/bugrakaann/msi-ultrapower/main/install.sh | bash
```

Para actualizar, ejecuta de nuevo el mismo comando. Para el ventilador, el modo del EC, Cooler Boost
y el límite de carga, instala también el controlador [msi-ec](https://github.com/BeardOverflow/msi-ec)
desde AUR (`msi-ec-dkms-git`) y reinicia. Sin él, todo lo demás sigue funcionando.

<details>
<summary>Instalación manual</summary>

```sh
git clone https://github.com/bugrakaann/msi-ultrapower.git
cd msi-ultrapower
make install
```

</details>

## Cómo se usa

1. Abre **Modos de energía** desde el menú de aplicaciones.
2. Elige un modo. La ventana muestra exactamente qué cambiará en tu portátil.
3. Pulsa **Aplicar** e introduce tu contraseña.

Para volver a como estaba todo antes de usar la aplicación, pulsa **Restaurar ajustes anteriores**.
Los modos de batería apagan la NVIDIA por completo tras reiniciar; la ventana te avisa cuando hace falta.

### Modos

| Modo | Qué hace |
|---|---|
| **Máximo rendimiento** | Perfil de rendimiento, turbo, Cooler Boost, frecuencia más alta, brillo al 100% |
| **Rendimiento · Ventilador manual** | Lo mismo, con tu propia curva de ventilador (se ajusta en MControlCenter) |
| **Equilibrado** | Perfil equilibrado, ventilador automático, brillo al 60%, la NVIDIA duerme en reposo |
| **Máxima batería** | Ahorro de energía, sin turbo, brillo al 30%, NVIDIA apagada, dispositivos en reposo, luz del teclado apagada |
| **Máxima batería · Hz bajos** | Lo mismo, además de la frecuencia más baja de la pantalla |

Las pantallas externas mantienen su resolución y frecuencia. Las salidas conectadas a la NVIDIA se
apagan en los modos de batería, porque la NVIDIA está apagada.

### Ajustes (⚙)

- **Límite de carga** – cargar la batería hasta el 60, 80 o 100%. Entre 60 y 80% alarga su vida útil.
- **Modo automático** – cambiar de modo al conectar o desconectar el cargador.
- **No pedir la contraseña de administrador** – sin contraseña para cambiar de modo, el límite de
  carga y el modo automático.
- **Iniciar en la bandeja del sistema al iniciar sesión** – cambia de modo y ve la batería, el consumo y las temperaturas desde la bandeja.
- **Opciones de los modos de batería** – dispositivos en reposo, apagar Bluetooth.
- **Idioma** – English, Türkçe, Русский, Español, العربية.

### Línea de comandos

```sh
msi-ultrapower balanced            # performance, performance-manual, balanced, battery, battery-low-hz
msi-ultrapower battery --dry-run   # mostrar qué cambiaría, sin cambiar nada
msi-ultrapower restore             # volver a los ajustes de antes del primer modo
msi-ultrapower charge 80           # límite de carga: 60, 80 o 100
msi-ultrapower status              # valores actuales
msi-ultrapower doctor              # qué funciona en este portátil
```

## Compatibilidad

Desarrollado en un MSI GF65 Thin 9SEXR. La aplicación no supone un solo modelo: detecta lo que
admite tu portátil (modos del EC y del ventilador, frecuencias de pantalla de 120 a 240 Hz, turbo de
Intel o AMD y si hay una NVIDIA). Lo que falta se omite y se muestra en la ventana.

- **Conmutador MUX:** si el modo de GPU del BIOS es *Discrete*, la NVIDIA controla la pantalla y la
  aplicación no la apagará. Elige *MSHybrid/Optimus* en el BIOS para usar los modos de batería por completo.
- **TLP, auto-cpufreq y tuned** entran en conflicto con los perfiles de energía; la aplicación avisa si alguno está en marcha.

Para contar cómo funciona en tu modelo,
[abre un issue](https://github.com/bugrakaann/msi-ultrapower/issues/new?template=model-report.md)
con la salida de `msi-ultrapower doctor`.

## Desinstalación

```sh
msi-ultrapower restore        # opcional: recuperar tus ajustes anteriores
sudo pacman -R msi-ultrapower
```

Tus ajustes se quedan en `~/.config/msi-ultrapower` y `~/.local/share/msi-ultrapower`.

## Solución de problemas

**El escritorio no arranca tras elegir un modo de batería.** Cambia a una consola de texto con
Ctrl+Alt+F3, inicia sesión y ejecuta:

```sh
sudo /usr/lib/msi-ultrapower/msi-ultrapower-gpu-boot hybrid
```

Después reinicia. Esto solo quita el bloqueo de NVIDIA que añadió msi-ultrapower.

**Algo falló.** Pulsa **Ver registro** en la ventana, o ejecuta el mismo modo desde una terminal
para ver la salida completa.

## Aviso legal

msi-ultrapower es un proyecto no oficial, sin relación con Micro-Star International (MSI) ni
respaldado por ella. Modifica ajustes del controlador integrado (EC), de los módulos del kernel y
del arranque; úsalo bajo tu propia responsabilidad. No se ofrece ninguna garantía.

## Licencia

[GPL-3.0-or-later](LICENSE)
