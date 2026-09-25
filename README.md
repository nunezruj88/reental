# Reental

Aplicación preparada para instalar en un LXC Linux con Nginx. Esta entrega no se ha instalado en el servidor: faltan acceso al LXC y el segundo dominio. No se ha modificado `/var/www/periodico` ni su configuración.

## Qué incluye

- Resumen responsive con recuentos, cobertura de relaciones y ranking por número de registros de alquiler.
- Carga conjunta y validada de ambos CSV; reemplazo atómico en SQLite, conservando el conjunto anterior ante errores de validación.
- Explorador con todas las columnas originales, búsqueda, paginación y grupos de registros relacionados.
- Compras: clave de primera columna. Alquiler: texto anterior al primer `#` de primera columna. Se recortan espacios exteriores, se conservan ceros iniciales y mayúsculas. Las claves vacías no coinciden. Los duplicados se muestran y no multiplican los recuentos.
- UTF-8/BOM o Windows-1252, separadores `, ; TAB |`, valores entrecomillados y multilínea. Se exige cabecera única y no vacía. Máximo 10 MB, 50.000 filas y 150 columnas por archivo.
- Persistencia del último conjunto válido; no incluye histórico de importaciones ni cuentas individuales. El acceso compartido se protege con contraseña en Nginx.

Se revisaron los CSV reales: contienen inversiones por inmueble y distribuciones de rendimientos. El dashboard añade sumas de `inversion`, `distributed`, `reinvested`, `claimed` y `retained`, gráficos por inmueble y mes, y avisos de fechas inconsistentes. Los cálculos usan decimales exactos en el backend y nunca suman `distributed` con su posible desglose. Los valores vacíos o inválidos hacen que el total afectado aparezca como no disponible, no como cero. Los CSV originales no están incluidos en el paquete.

Pendiente confirmar moneda, si `periodo` está en meses y si los campos de retorno son porcentajes. Hasta entonces se muestran sus valores originales, sin previsiones ni beneficio neto. Los recuentos de alquiler son filas, no se presupone que cada fila sea una transacción. Las rutas, usuario y servicio usan el nombre `reental`.

## Arquitectura y aislamiento

```text
Segundo dominio → Nginx (80/HTTPS o Tunnel) → 127.0.0.1:8091
                                            └─ /var/www/reental
Datos: /var/lib/reental/reental.sqlite3
Servicio: reental.service · Usuario: reental
```

El puerto 8091 distingue el backend de la web existente. El dominio distingue qué sitio elige Nginx. No se añade `default_server`, no se sustituye el sitio predeterminado ni se abre 8091 a Internet. Debe comprobarse que 8091 está libre antes de instalar.

## Prueba local (Python 3.10 o posterior)

Desde esta carpeta:

```sh
python -m unittest discover -s tests -v
python app.py
```

Abrir `http://127.0.0.1:8091`. El servidor local es solo para pruebas; en Linux se usa Gunicorn. Los archivos CSV no se sirven como archivos públicos. No usar datos reales en una publicación sin protección de acceso y HTTPS.

## Instalación en Debian/Ubuntu: revisar primero

Ejecutar en el LXC como administrador. Antes, copiar esta carpeta a `/tmp/reental`. Los comandos de instalación presuponen que las rutas y el usuario de Reental no existen todavía; si existen, revisar antes de copiar. No tocar los archivos del periódico.

```sh
ss -ltnp 'sport = :8091'
nginx -t
nginx -T > /root/nginx-antes-reental.txt 2>&1
```

Si el puerto está ocupado, elegir otro puerto libre y cambiarlo tanto en `deploy/reental.service` como en `deploy/reental.nginx.conf`. Guardar también una respuesta HTTP de la web existente usando su dominio real, para compararla después.

```sh
apt-get install python3-venv apache2-utils
useradd --system --home /var/lib/reental --shell /usr/sbin/nologin reental
install -d -m 755 /var/www/reental
cp -r /tmp/reental/. /var/www/reental/
python3 -m venv /var/www/reental/.venv
/var/www/reental/.venv/bin/pip install -r /var/www/reental/requirements.txt
cp /var/www/reental/deploy/reental.service /etc/systemd/system/reental.service
systemctl daemon-reload
systemctl enable --now reental
curl --fail http://127.0.0.1:8091/health
```

El servicio crea su directorio privado de datos mediante `StateDirectory`. El código permanece propiedad del administrador. Ver registros con `journalctl -u reental -n 50`.

## Segundo sitio Nginx

1. Cambiar **solo** `reental.example.com` en la plantilla por el dominio nuevo, distinto del periódico. Comprobar con `nginx -T` que ese nombre no está ya configurado. Nginx debe incluir `sites-enabled` (distribuciones Debian/Ubuntu habituales).
2. Crear una contraseña de acceso (se pide de forma interactiva):

```sh
htpasswd -c /etc/nginx/reental.htpasswd administrador
chown root:www-data /etc/nginx/reental.htpasswd
chmod 640 /etc/nginx/reental.htpasswd
cp /var/www/reental/deploy/reental.nginx.conf /etc/nginx/sites-available/reental
ln -s /etc/nginx/sites-available/reental /etc/nginx/sites-enabled/reental
nginx -t
```

Usar el grupo real de los trabajadores de Nginx si no es `www-data`. No reutilizar `htpasswd -c` en futuras actualizaciones: recrearía ese fichero de contraseñas.

3. **Solo si `nginx -t` termina correctamente**, recargar sin reiniciar:

```sh
systemctl reload nginx
curl -I -H 'Host: reental.example.com' http://127.0.0.1/
curl --fail -u administrador -H 'Host: reental.example.com' http://127.0.0.1/health
```

La primera petición debe devolver 401 y la segunda, tras introducir contraseña, `{"status":"ok"}`. Sustituir el dominio también en las pruebas. Confirmar que el periódico sigue respondiendo como antes y probar una carga de CSV desde el navegador.

## Cloudflare Tunnel o HTTPS

Si ya hay Cloudflare Tunnel, añadir una ruta de hostname público con el nuevo dominio hacia `http://127.0.0.1:80` cuando el túnel corre dentro del mismo LXC, o hacia `http://10.8.1.106:80` si corre fuera y esa sigue siendo la IP del LXC. El encabezado HTTP Host debe ser el dominio nuevo. Mantener las rutas existentes y el cierre de reglas del túnel. No apuntar el túnel directamente al 8091: se omitiría la autenticación de Nginx. Acceder por HTTPS en el dominio público.

Si no hay Tunnel, configurar DNS y un certificado HTTPS para el dominio nuevo antes de enviar credenciales o datos por Internet. La plantilla suministrada cubre el origen HTTP detrás de Tunnel; no incluye un certificado inventado ni cambia TLS del periódico.

## Copia y retirada

Antes de reemplazar datos importantes, hacer copia consistente con Python/SQLite backup o con `sqlite3 /var/lib/reental/reental.sqlite3 ".backup '/ruta/privada/reental-backup.sqlite3'"`. Mantener privada la copia. La importación sustituye el conjunto anterior y no guarda histórico.

Para desactivar únicamente Reental: quitar el enlace `/etc/nginx/sites-enabled/reental`, ejecutar `nginx -t` y, si pasa, recargar Nginx; después `systemctl disable --now reental`. Conservar el directorio de datos. No eliminar ni editar otros sitios.

Referencia oficial usada para la configuración: https://nginx.org/en/docs/http/ngx_http_proxy_module.html y https://nginx.org/en/docs/http/server_names.html.
