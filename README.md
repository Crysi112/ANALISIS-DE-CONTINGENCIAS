


Aquí tienes el texto listo. Solo haz clic en el botón **"Copiar código"** (en la esquina superior derecha del recuadro negro) y pégalo directamente en el archivo `README.md` de tu repositorio en GitHub:

```markdown
# ⚡ EMS: Analizador de Seguridad de Redes de Potencia

Este proyecto es un simulador avanzado de **Sistemas de Gestión de Energía (EMS)** diseñado para Centros de Control de redes eléctricas. Realiza cálculos de flujos de potencia, estimación de estado y análisis predictivo de seguridad (Criterio N-1) en tiempo real mediante aproximaciones lineales (Flujo de C.D.) y cálculo exacto de factores de sensibilidad matriciales.

## 🚀 Características Principales

* **Flujo de Potencia de C.D. Exacto**: Cálculo instantáneo de ángulos de fase y flujos activos construyendo la matriz de susceptancia `[B]` y su inversa `[F]`.
* **Estimador de Estado WLS**: Simula mediciones ruidosas típicas de un sistema SCADA real y las filtra utilizando el algoritmo estadístico de Mínimos Cuadrados Ponderados (Weighted Least Squares).
* **Análisis de Contingencias N-k y Cascadas**: Permite al operador desconectar múltiples líneas, generadores o cargas simultáneamente, evaluando si el nuevo flujo de potencia provoca sobrecargas térmicas y desconexiones en cascada.
* **Proyección de Seguridad N-1 (Fuerza Bruta Inteligente)**: Evalúa en milisegundos qué pasaría si *cualquier* elemento del sistema fallara en el estado actual, alertando de posibles vulnerabilidades futuras.
* **Matrices de Sensibilidad Inteligentes**:
  * **GSF (Generation Shift Factors)**: Calcula y resalta qué generadores afectan positiva o negativamente a qué líneas.
  * **LODF (Line Outage Distribution Factors)**: Muestra el porcentaje de flujo que absorberá una línea si otra se desconecta.
* **Interfaz Gráfica Profesional (GUI)**: Construida con `PyQt6`. Presenta tablas elásticas (sin scrollbars molestos), edición en tiempo real, alertas con códigos de colores (verde, naranja, rojo) y una bitácora de eventos.
* **Lector CSV Tolerante a Fallos**: Lector inteligente que soporta múltiples delimitadores, formatos numéricos europeos/americanos y detecta automáticamente si las potencias están ingresadas en M.W. o en por unidad (p.u.).

---

## 🛠️ Requisitos e Instalación

El programa está escrito en **Python 3.8+**. Para ejecutarlo, solo necesitas instalar las librerías matemáticas y gráficas base.

1. Abre tu terminal o símbolo del sistema (CMD/PowerShell).
2. Ejecuta el siguiente comando para instalar las dependencias:

```bash
pip install numpy PyQt6
```

3. Ejecuta la aplicación:

```bash
python ems_analizador.py
```

*(Asegúrate de nombrar tu archivo de Python como `ems_analizador.py` o sustitúyelo por el nombre real de tu script).*

---

## 📖 Guía de Uso Rápido

1. **Cargar la Topología (CSV)**
   Haz clic en el botón `Cargar Topología` y selecciona tu archivo CSV o Excel exportado. El programa leerá nodos, líneas, reactancias, límites de potencia y estados de generación.
   
2. **Edición Manual**
   Puedes modificar directamente cualquier valor en las pestañas **Líneas de Transmisión** y **Nodos y Generadores**. Al presionar *Enter* o cambiar un *Checkbox*, el sistema recalculará todo instantáneamente.

3. **Simular Contingencias**
   En la barra superior de "Simular Contingencia", puedes ingresar fallas separadas por comas. Ejemplos válidos:
   * `l1-4` : Desconecta la línea entre el nodo 1 y 4.
   * `g2` : Desconecta el generador ubicado en el nodo 2.
   * `c3` : Desconecta la carga ubicada en el nodo 3.
   * Combinación: `l1-4, g2` (Desconecta ambos a la vez).

4. **Análisis de Resultados**
   * **Tabla de Flujos (Izquierda)**: Compara el estado Base, lo que lee el SCADA, el flujo Real actual, el límite de la línea y cuál es el máximo Riesgo si ocurre un evento N-1 extra.
   * **Consola Predictiva (Abajo)**: Muestra el historial de cascadas, identificando exactamente qué línea causaría un colapso y a cuántos MW se elevaría el flujo.
   * **Matrices GSF y LODF (Derecha)**: Las celdas en **rojo brillante** indican factores críticos en líneas que se encuentran actualmente al borde del colapso térmico. Úsalas para decidir qué generador subir/bajar para aliviar la congestión.

---

## 📊 Formato del Archivo CSV

El programa tiene un analizador de texto muy flexible, pero se recomienda que el archivo `.csv` contenga las siguientes columnas (no importa el orden ni las mayúsculas/minúsculas):

**Para Líneas:**
* `From Bus` o `Nodo Envio`
* `To Bus` o `Nodo Recibo`
* `X(pu)` o `Reactancia` (Obligatorio)
* `R(pu)` o `Resistencia`
* `BCAP(pu)`
* `Limit MW` o `Limite Potencia` (Si es 0, no se monitorearán sobrecargas).

**Para Nodos (Buses):**
* `Bus` o `Nodo`
* `Tipo` (Gen, Load, Swing)
* `Pgen` o `Pg` (Potencia generada).
* `Pmax` (Límite máximo del generador para redistribución AGC).
* `Pload` o `Pl` (Carga).
* `PF` o `Participacion` (Factor de participación del generador ante pérdidas).

*(Nota: Si los valores de potencia Pgen/Pload en el archivo son muy pequeños -menores a 20-, el programa asumirá inteligentemente que están en p.u. y los multiplicará por la potencia base del sistema, que por defecto es 100 MVA).*

---

## 🧮 Fundamento Matemático

El núcleo de este software ignora simplificaciones de libros básicos y calcula los valores basándose en el análisis topológico matricial exacto implementado en centros de control reales:

1. **Matriz B**: $B_{im} = -1/x_{im}$ y $B_{ii} = \sum 1/x_{im}$.
2. **Matriz F**: $[F] = [B_{reducida}]^{-1}$.
3. **Flujos DC**: $f_{im} = \frac{1}{x_{im}} (\theta_i - \theta_m)$.
4. **GSF**: $a_{li} = \frac{1}{x_l} (F_{ki} - F_{mi})$.
5. **LODF**: $d_{k,l} = \frac{x_l}{x_k} \left[ \frac{(F_{vi} - F_{vm}) - (F_{wi} - F_{wm})}{x_l - (F_{ii} + F_{mm} - 2F_{im})} \right]$.

---

**Desarrollado para Ingeniería de Sistemas Eléctricos de Potencia.**
```

*(Nota: GitHub soporta nativamente la notación matemática con `$` que he puesto al final, por lo que las fórmulas se renderizarán correctamente y con aspecto profesional en tu repositorio).*
