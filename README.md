# Monitoreo de Bosques Bogotá

Este repositorio contiene herramientas y scripts para el análisis y monitoreo de los bosques en Bogotá, integrando diversas fuentes de datos satelitales y funcionalidades para el seguimiento de la cobertura terrestre y la deforestación.

## Novedades Recientes

Últimamente se han fusionado dos ramas principales que aportan nuevas funcionalidades:

- **Urban Sprawl** ([Pull Request](https://github.com/Metodos-Mixtos/bosques-bog/pull/2)):  
  Se han añadido herramientas para analizar la expansión urbana y su impacto sobre los bosques, utilizando datos de Dynamic World y comparativas temporales.

- **Reportes de Deforestación** ([Pull Request](https://github.com/Metodos-Mixtos/bosques-bog/pull/1)):  
  Ahora el repositorio permite generar y visualizar reportes sobre la deforestación, facilitando el seguimiento y la toma de decisiones basadas en datos satelitales y alertas.
  Proyecto gfw_alerts

  Este proyecto se conecta a la API de Global Forest Watch (GFW) para descargar alertas integradas 
  de deforestación que combinan tres subsistemas: GLAD-L, GLAD-S2 y RADD, según una fecha y un polígono 
  definidos.

  El script guarda los resultados en un archivo CSV, genera un archivo JSON con el resumen estadístico 
  por tipo de alerta, y crea un mapa mostrandos las alertas en el área de referencia.


## Estructura del Repositorio

- `dynamic_world/`: Scripts para el análisis de cobertura terrestre con Dynamic World.
Este proyecto descarga los mapas de cobertura terrestre de Dynamic World disponibles en 
Google Earth Engine para dos trimestres de referencia y un área definida.

Además, crea una grilla de 100 m × 100 m sobre el área de estudio para calcular estadísticas 
zonales de ambos periodos y estimar el cambio porcentual entre ellos. Finalmente, genera un mapa de coberturas del suelo para los dos trimestres seleccionados.

- `sentinel-images-download/`: Código para la descarga y procesamiento de imágenes satelitales Sentinel.
- Otros submódulos y utilidades relacionadas con el monitoreo de bosques.

## Uso

Consulta los README específicos de cada subcarpeta para instrucciones detalladas sobre instalación y uso.

## Colaboradores

Este proyecto es mantenido por el equipo de Métodos Mixtos y colaboradores.  
Para sugerencias o reportar problemas, crea un Issue o Pull Request.

## Set-up

#Las bases de datos están en Teams en en el canal GIS en
#data_folder = 'GIS/geoinfo/Colombia/Bogotá/bosques_bogota'
#'https://metodosmixtos.sharepoint.com/:f:/s/MMC-General/EogKVdk7FYZBsTKCr79IK98BgnozkrY1czyiyR6MDn5i5g?e=78hsPW'

Para instalar el ambiente de programación, lo mejor es: 

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

El .env file hay que crearlo con la información que está en: 
'MMC - General - SDP - Monitoreo de Bosques/monitoreo_bosques/dot_env_content.txt'

## Licencia

La licencia es pública. El código es de propiedad de la Secretaría Distrital de Planeación de Bogotá.