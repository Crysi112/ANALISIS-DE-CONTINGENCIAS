import sys
import csv
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Set

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QTabWidget, QTableWidget, 
    QTableWidgetItem, QSplitter, QFileDialog, QMessageBox, QListWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QHeaderView

POTENCIA_BASE_MVA = 100.0
RUTA_CSV_POR_DEFECTO = ""

@dataclass
class LineaTransmision:
    nodo_origen: int
    nodo_destino: int
    resistencia_pu: float
    reactancia_pu: float
    susceptancia_shunt_pu: float
    potencia_base_origen_mw: float
    potencia_base_destino_mw: float
    activa: bool
    nombre: str
    limite_potencia_mw: float = 0.0

@dataclass
class NodoElectrico:
    id: int
    tipo: str
    voltaje_programado: float
    potencia_generada_mw: float
    potencia_carga_mw: float
    potencia_reactiva_mvar: float
    generador_activo: bool
    potencia_maxima_mw: float = 1000.0
    factor_participacion: float = 1.0

@dataclass
class ResultadosSistema:
    matriz_b: np.ndarray
    matriz_f: np.ndarray
    matriz_gsf: np.ndarray
    matriz_lodf: np.ndarray
    flujos_mw: List[float]
    angulos_radianes: List[float]
    topologia_valida: bool
    mediciones_scada_ruido: List[float] = None
    flujos_estimados_wls: List[float] = None

def convertir_texto_a_numero(texto: str) -> Optional[float]:
    if not texto or not str(texto).strip(): 
        return None
    texto = str(texto).strip().replace(" ", "")
    if '.' in texto and ',' in texto: 
        texto = texto.replace('.', '').replace(',', '.')
    elif ',' in texto and '.' not in texto: 
        texto = texto.replace(',', '.')
    try: 
        return float(texto)
    except ValueError: 
        return None

def detectar_delimitador(primera_linea: str) -> str:
    for delimitador in[',', ';', '\t']:
        if primera_linea.count(delimitador) > 2: 
            return delimitador
    return ','

def limpiar_saltos_linea_csv(contenido: str) -> str:
    texto_limpio =[]
    dentro_de_comillas = False
    caracter_previo = '\0'
    for caracter in contenido:
        if caracter == '"': 
            dentro_de_comillas = not dentro_de_comillas
            texto_limpio.append(caracter)
        elif caracter in ('\n', '\r'):
            if dentro_de_comillas:
                if caracter == '\n' and caracter_previo != '\r': 
                    texto_limpio.append(' ')
            else: 
                texto_limpio.append(caracter)
            caracter_previo = caracter
            continue
        else: 
            texto_limpio.append(caracter)
        caracter_previo = caracter
    return "".join(texto_limpio)

def buscar_columna(fila_csv: dict, nombres_posibles: list) -> str:
    for clave in fila_csv.keys():
        if not clave: 
            continue
        clave_normalizada = " ".join(clave.strip().lower().replace("\n", " ").split())
        if clave_normalizada in nombres_posibles: 
            return fila_csv[clave]
    for clave in fila_csv.keys():
        if not clave: 
            continue
        clave_normalizada = " ".join(clave.strip().lower().replace("\n", " ").split())
        for posible_nombre in nombres_posibles:
            if posible_nombre == "bus" and ("from" in clave_normalizada or "to" in clave_normalizada): 
                continue
            if posible_nombre in clave_normalizada: 
                return fila_csv[clave]
    return ""

def cargar_topologia(ruta_archivo: str) -> Tuple[List[LineaTransmision], List[NodoElectrico]]:
    try:
        with open(ruta_archivo, 'r', encoding='utf-8-sig') as archivo: 
            contenido_crudo = archivo.read()
    except Exception:
        with open(ruta_archivo, 'r', encoding='latin1') as archivo: 
            contenido_crudo = archivo.read()
    lineas_texto = contenido_crudo.splitlines()
    if not lineas_texto: 
        return [],[]
    delimitador = detectar_delimitador(next((l for l in lineas_texto if l.strip()), ""))
    contenido_limpio = limpiar_saltos_linea_csv(contenido_crudo)
    lector_csv = csv.DictReader(contenido_limpio.splitlines(), delimiter=delimitador)
    lista_lineas =[]
    diccionario_nodos = {}
    for fila in lector_csv:
        origen_val = convertir_texto_a_numero(buscar_columna(fila, ["from bus", "frombus", "from", "nodo envio"]))
        destino_val = convertir_texto_a_numero(buscar_columna(fila,["to bus", "tobus", "to", "nodo recibo"]))
        reactancia_val = convertir_texto_a_numero(buscar_columna(fila,["x(pu)", "x (pu)", "x", "reactancia"]))
        if origen_val is not None and destino_val is not None and reactancia_val is not None and reactancia_val > 0.0:
            p_from = convertir_texto_a_numero(buscar_columna(fila, ["p0(mw) from", "p0 from"])) or 0.0
            p_to = convertir_texto_a_numero(buscar_columna(fila, ["p0(mw) to", "p0 to"])) or 0.0
            limite = convertir_texto_a_numero(buscar_columna(fila,["limit", "limit mw", "limite potencia", "limite"])) or 0.0
            resistencia_val = max(convertir_texto_a_numero(buscar_columna(fila,["r(pu)", "r (pu)", "r"])) or 0.0, 0.0)
            bcap_val = convertir_texto_a_numero(buscar_columna(fila, ["bcap(pu)", "bcap (pu)", "bcap"])) or 0.0
            nueva_linea = LineaTransmision(
                nodo_origen=int(origen_val), 
                nodo_destino=int(destino_val), 
                reactancia_pu=reactancia_val,
                resistencia_pu=resistencia_val, 
                susceptancia_shunt_pu=bcap_val, 
                potencia_base_origen_mw=p_from, 
                potencia_base_destino_mw=p_to, 
                activa=True, 
                nombre=f"{int(origen_val)}-{int(destino_val)}", 
                limite_potencia_mw=limite
            )
            lista_lineas.append(nueva_linea)
        id_nodo_val = convertir_texto_a_numero(buscar_columna(fila, ["bus", "busnum", "nodo"]))
        if id_nodo_val is not None:
            id_nodo = int(id_nodo_val)
            pot_gen = convertir_texto_a_numero(buscar_columna(fila, ["pgen", "pg"])) or 0.0
            pot_max = convertir_texto_a_numero(buscar_columna(fila,["pmax", "p_max"])) or (pot_gen * 1.5 if pot_gen > 0 else 1000.0)
            fac_part = convertir_texto_a_numero(buscar_columna(fila, ["pf", "participacion"])) or (pot_max if pot_max > 0 else 1.0)
            tipo_nodo = buscar_columna(fila, ["tipo", "type"]) or "Load"
            voltaje = max(0.5, min(1.5, convertir_texto_a_numero(buscar_columna(fila, ["voltage schedule", "v sched"])) or 1.0))
            pot_carga = max(convertir_texto_a_numero(buscar_columna(fila, ["pload", "pl"])) or 0.0, 0.0)
            react_carga = convertir_texto_a_numero(buscar_columna(fila, ["qload", "ql"])) or 0.0
            nuevo_nodo = NodoElectrico(
                id=id_nodo, 
                tipo=tipo_nodo, 
                voltaje_programado=voltaje, 
                potencia_generada_mw=pot_gen, 
                potencia_carga_mw=pot_carga, 
                potencia_reactiva_mvar=react_carga, 
                generador_activo=True, 
                potencia_maxima_mw=pot_max, 
                factor_participacion=fac_part
            )
            diccionario_nodos[id_nodo] = nuevo_nodo
    lista_nodos = list(diccionario_nodos.values())
    lista_nodos.sort(key=lambda b: b.id)
    maxima_potencia_encontrada = max([n.potencia_generada_mw for n in lista_nodos] +[n.potencia_carga_mw for n in lista_nodos] + [0.0])
    if 0.0 < maxima_potencia_encontrada <= 20.0:
        for nodo in lista_nodos:
            nodo.potencia_generada_mw *= POTENCIA_BASE_MVA
            nodo.potencia_carga_mw *= POTENCIA_BASE_MVA
            if nodo.potencia_maxima_mw <= 20.0:
                nodo.potencia_maxima_mw *= POTENCIA_BASE_MVA
    return lista_lineas, lista_nodos

class VentanaCentroControl(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EMS")
        self.resize(1600, 1000)
        self.showMaximized()
        self.lista_lineas: List[LineaTransmision] = []
        self.lista_nodos: List[NodoElectrico] = []
        self.mapa_indices_nodos: Dict[int, int] = {}
        self.resultado_base: Optional[ResultadosSistema] = None
        self.resultado_actual: Optional[ResultadosSistema] = None
        self.riesgos_futuros_n_1: List[float] =[] 
        self.texto_comando_fallas = ""
        self.interfaz_bloqueada = False
        self.construir_interfaz()
        try:
            lineas_cargadas, nodos_cargados = cargar_topologia(RUTA_CSV_POR_DEFECTO)
            if lineas_cargadas and nodos_cargados:
                self.lista_lineas = lineas_cargadas
                self.lista_nodos = nodos_cargados
        except Exception:
            pass
        self.ejecutar_analisis_completo()

    def construir_interfaz(self):
        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        diseno_principal = QVBoxLayout(widget_central)
        diseno_superior = QHBoxLayout()
        etiqueta_titulo = QLabel("EMS: Panel de Operacion y Seguridad")
        etiqueta_titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        diseno_superior.addWidget(etiqueta_titulo)
        boton_cargar = QPushButton("Cargar Topologia")
        boton_cargar.clicked.connect(self.evento_cargar_archivo)
        boton_recalcular = QPushButton("Forzar Recalculo")
        boton_recalcular.clicked.connect(self.ejecutar_analisis_completo)
        boton_limpiar = QPushButton("Restablecer Red")
        boton_limpiar.clicked.connect(self.evento_limpiar_sistema)
        diseno_superior.addWidget(boton_cargar)
        diseno_superior.addWidget(boton_recalcular)
        diseno_superior.addWidget(boton_limpiar)
        diseno_superior.addStretch()
        diseno_principal.addLayout(diseno_superior)
        diseno_contingencias = QHBoxLayout()
        diseno_contingencias.addWidget(QLabel("Simular Contingencia (ej: l1-4, g2, c3):"))
        self.input_comandos_falla = QLineEdit()
        self.input_comandos_falla.setFixedWidth(500)
        self.input_comandos_falla.textChanged.connect(self.evento_texto_fallas_modificado)
        diseno_contingencias.addWidget(self.input_comandos_falla)
        diseno_contingencias.addStretch()
        diseno_principal.addLayout(diseno_contingencias)
        self.etiqueta_estado_sistema = QLabel("")
        self.etiqueta_estado_sistema.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        diseno_principal.addWidget(self.etiqueta_estado_sistema)
        divisor_paneles = QSplitter(Qt.Orientation.Vertical)
        diseno_principal.addWidget(divisor_paneles)
        pestanas_editor = QTabWidget()
        panel_lineas = QWidget()
        layout_lineas = QVBoxLayout(panel_lineas)
        boton_agregar_linea = QPushButton("Insertar Linea Nueva")
        boton_agregar_linea.clicked.connect(self.evento_agregar_linea)
        layout_lineas.addWidget(boton_agregar_linea)
        self.tabla_lineas = QTableWidget()
        self.tabla_lineas.cellChanged.connect(self.evento_edicion_tabla_lineas)
        layout_lineas.addWidget(self.tabla_lineas)
        pestanas_editor.addTab(panel_lineas, "Lineas de Transmision")
        panel_nodos = QWidget()
        layout_nodos = QVBoxLayout(panel_nodos)
        boton_agregar_nodo = QPushButton("Insertar Nodo Nuevo")
        boton_agregar_nodo.clicked.connect(self.evento_agregar_nodo)
        layout_nodos.addWidget(boton_agregar_nodo)
        self.tabla_nodos = QTableWidget()
        self.tabla_nodos.cellChanged.connect(self.evento_edicion_tabla_nodos)
        layout_nodos.addWidget(self.tabla_nodos)
        pestanas_editor.addTab(panel_nodos, "Nodos y Generadores")
        divisor_paneles.addWidget(pestanas_editor)
        panel_resultados = QWidget()
        layout_resultados = QVBoxLayout(panel_resultados)
        cuadricula_resultados = QHBoxLayout()
        columna_izq = QVBoxLayout()
        columna_izq.addWidget(QLabel("Flujos de Potencia y Alertas N-1 (MW)"))
        self.tabla_flujos = QTableWidget()
        columna_izq.addWidget(self.tabla_flujos)
        columna_izq.addWidget(QLabel("Matriz B (Susceptancia)"))
        self.tabla_matriz_b = QTableWidget()
        columna_izq.addWidget(self.tabla_matriz_b)
        cuadricula_resultados.addLayout(columna_izq)
        columna_der = QVBoxLayout()
        columna_der.addWidget(QLabel("Matriz F (Inversa de B)"))
        self.tabla_matriz_f = QTableWidget()
        columna_der.addWidget(self.tabla_matriz_f)
        columna_der.addWidget(QLabel("Matriz GSF (Participacion)"))
        self.tabla_gsf = QTableWidget()
        columna_der.addWidget(self.tabla_gsf)
        columna_der.addWidget(QLabel("Matriz LODF (Distribucion)"))
        self.tabla_lodf = QTableWidget()
        columna_der.addWidget(self.tabla_lodf)
        cuadricula_resultados.addLayout(columna_der)
        layout_resultados.addLayout(cuadricula_resultados)
        divisor_paneles.addWidget(panel_resultados)
        panel_consola = QWidget()
        layout_consola = QVBoxLayout(panel_consola)
        layout_consola.addWidget(QLabel("Consola de Analisis Predictivo y Cascadas"))
        self.lista_consola = QListWidget()
        self.lista_consola.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas; font-size: 10pt;")
        layout_consola.addWidget(self.lista_consola)
        divisor_paneles.addWidget(panel_consola)
        divisor_paneles.setSizes([300, 550, 150])

    def evento_cargar_archivo(self):
        ruta_archivo, _ = QFileDialog.getOpenFileName(self, "Abrir Topologia", "", "CSV Files (*.csv)")
        if ruta_archivo:
            try:
                lineas_leidas, nodos_leidos = cargar_topologia(ruta_archivo)
                if lineas_leidas and nodos_leidos:
                    self.lista_lineas = lineas_leidas
                    self.lista_nodos = nodos_leidos
                    self.ejecutar_analisis_completo()
            except Exception as e:
                QMessageBox.critical(self, "Error al leer", str(e))

    def evento_limpiar_sistema(self):
        self.lista_lineas.clear()
        self.lista_nodos.clear()
        self.mapa_indices_nodos.clear()
        self.resultado_base = None
        self.resultado_actual = None
        self.riesgos_futuros_n_1.clear()
        self.input_comandos_falla.blockSignals(True)
        self.input_comandos_falla.clear()
        self.texto_comando_fallas = ""
        self.input_comandos_falla.blockSignals(False)
        self.lista_consola.clear()
        self.tabla_lineas.setRowCount(0)
        self.tabla_nodos.setRowCount(0)
        self.tabla_flujos.setRowCount(0)
        self.tabla_matriz_b.setRowCount(0)
        self.tabla_matriz_f.setRowCount(0)
        self.tabla_gsf.setRowCount(0)
        self.tabla_lodf.setRowCount(0)
        self.etiqueta_estado_sistema.setText("Sistema reiniciado a valores de fabrica.")
        self.actualizar_tablas_edicion()

    def evento_texto_fallas_modificado(self, texto: str):
        self.texto_comando_fallas = texto
        self.ejecutar_analisis_completo()

    def clasificar_comandos_falla(self) -> Tuple[Set[str], Set[int], Set[int]]:
        fallas_lineas = set()
        fallas_generadores = set()
        fallas_cargas = set()
        comandos = self.texto_comando_fallas.replace(" ", "").split(',')
        for comando in comandos:
            if not comando: 
                continue
            if comando.startswith('l'): 
                fallas_lineas.add(comando[1:])
            elif comando.startswith('g'): 
                try: fallas_generadores.add(int(comando[1:]))
                except ValueError: pass
            elif comando.startswith('c'): 
                try: fallas_cargas.add(int(comando[1:]))
                except ValueError: pass
            elif '-' in comando: 
                fallas_lineas.add(comando)
        return fallas_lineas, fallas_generadores, fallas_cargas

    def ejecutar_analisis_completo(self):
        self.lista_nodos.sort(key=lambda n: n.id)
        self.mapa_indices_nodos = {nodo.id: indice for indice, nodo in enumerate(self.lista_nodos)}
        if len(self.lista_nodos) < 2: 
            return
        self.resultado_base = self.calcular_flujo_dc_potencia(set(), set(), set())
        if self.resultado_base and self.resultado_base.topologia_valida:
            flujos_ruidosos, flujos_filtrados = self.algoritmo_wls_estimacion(self.resultado_base)
            self.resultado_base.mediciones_scada_ruido = flujos_ruidosos
            self.resultado_base.flujos_estimados_wls = flujos_filtrados
        fallas_lin, fallas_gen, fallas_car = self.clasificar_comandos_falla()
        self.simular_propagacion_cascadas(fallas_lin, fallas_gen, fallas_car)
        self.simular_prediccion_contingencias_n_1(fallas_lin, fallas_gen, fallas_car)
        self.actualizar_tablas_edicion()
        self.actualizar_pantalla_resultados()

    def simular_propagacion_cascadas(self, lineas_caidas: Set[str], generadores_caidos: Set[int], cargas_caidas: Set[int]):
        self.lista_consola.clear()
        lineas_abiertas = set(lineas_caidas)
        estado_convergente = None
        numero_iteracion = 1
        if not lineas_abiertas and not generadores_caidos and not cargas_caidas:
            self.lista_consola.addItem("Operacion normal estatica de la red.")
            self.resultado_actual = self.calcular_flujo_dc_potencia(set(), set(), set())
            return
        self.lista_consola.addItem("Iniciando evaluacion de contingencias y protecciones...")
        while True:
            resultado_iter = self.calcular_flujo_dc_potencia(lineas_abiertas, generadores_caidos, cargas_caidas)
            if not resultado_iter or not resultado_iter.topologia_valida:
                self.lista_consola.addItem(f"Iteracion {numero_iteracion}: Se detecto Isla Electrica. Colapso.")
                estado_convergente = resultado_iter
                break
            lineas_quemadas_ahora = set()
            for indice, linea in enumerate(self.lista_lineas):
                nombre_linea = f"{linea.nodo_origen}-{linea.nodo_destino}"
                if linea.activa and nombre_linea not in lineas_abiertas:
                    flujo_pasando = abs(resultado_iter.flujos_mw[indice])
                    if linea.limite_potencia_mw > 0.0 and flujo_pasando > linea.limite_potencia_mw:
                        lineas_quemadas_ahora.add(nombre_linea)
                        mensaje = f"Iteracion {numero_iteracion}: Sobrecarga en linea {nombre_linea}. Flujo: {flujo_pasando:.1f} MW Limite: {linea.limite_potencia_mw} MW"
                        self.lista_consola.addItem(mensaje)
            if not lineas_quemadas_ahora:
                if numero_iteracion > 1:
                    self.lista_consola.addItem("La red alcanzo un nuevo punto de equilibrio estable.")
                estado_convergente = resultado_iter
                break
            lineas_abiertas.update(lineas_quemadas_ahora)
            numero_iteracion += 1
        self.resultado_actual = estado_convergente

    def simular_prediccion_contingencias_n_1(self, lineas_caidas: Set[str], generadores_caidos: Set[int], cargas_caidas: Set[int]):
        if not self.resultado_actual or not self.resultado_actual.topologia_valida:
            self.riesgos_futuros_n_1 = [0.0] * len(self.lista_lineas)
            return
        self.lista_consola.addItem("")
        self.lista_consola.addItem("PROYECCION DE SEGURIDAD PREVENTIVA N-1")
        conteo_vulnerabilidades = 0
        self.riesgos_futuros_n_1 =[abs(flujo) for flujo in self.resultado_actual.flujos_mw]
        for j, linea_falla_hipotetica in enumerate(self.lista_lineas):
            nombre_out = f"{linea_falla_hipotetica.nodo_origen}-{linea_falla_hipotetica.nodo_destino}"
            if not linea_falla_hipotetica.activa or nombre_out in lineas_caidas: 
                continue
            flujo_previo_linea_j = self.resultado_actual.flujos_mw[j]
            for i, linea_monitoreada in enumerate(self.lista_lineas):
                if i == j or not linea_monitoreada.activa or f"{linea_monitoreada.nodo_origen}-{linea_monitoreada.nodo_destino}" in lineas_caidas: 
                    continue
                factor_distribucion = self.resultado_actual.matriz_lodf[i, j]
                flujo_post_falla = self.resultado_actual.flujos_mw[i] + factor_distribucion * flujo_previo_linea_j
                self.riesgos_futuros_n_1[i] = max(self.riesgos_futuros_n_1[i], abs(flujo_post_falla))
                if linea_monitoreada.limite_potencia_mw > 0.0 and abs(flujo_post_falla) > linea_monitoreada.limite_potencia_mw:
                    conteo_vulnerabilidades += 1
                    mensaje = f"RIESGO DETECTADO: Si cae la linea {nombre_out}, se sobrecargara la linea {linea_monitoreada.nodo_origen}-{linea_monitoreada.nodo_destino} a {abs(flujo_post_falla):.1f} MW."
                    self.lista_consola.addItem(mensaje)
        for nodo_gen in self.lista_nodos:
            if not nodo_gen.generador_activo or nodo_gen.potencia_generada_mw <= 0 or nodo_gen.id in generadores_caidos: 
                continue
            potencia_perdida = -nodo_gen.potencia_generada_mw
            indice_gen_caido = self.mapa_indices_nodos[nodo_gen.id]
            suma_participacion = sum(n.factor_participacion for n in self.lista_nodos if n.generador_activo and n.id not in generadores_caidos and n.id != nodo_gen.id)
            for k, linea_monitoreada in enumerate(self.lista_lineas):
                if not linea_monitoreada.activa or f"{linea_monitoreada.nodo_origen}-{linea_monitoreada.nodo_destino}" in lineas_caidas: 
                    continue
                flujo_post_falla = self.resultado_actual.flujos_mw[k] + self.resultado_actual.matriz_gsf[k, indice_gen_caido] * potencia_perdida
                if suma_participacion > 0:
                    for nodo_compensador in self.lista_nodos:
                        if nodo_compensador.generador_activo and nodo_compensador.id not in generadores_caidos and nodo_compensador.id != nodo_gen.id:
                            factor_gamma = nodo_compensador.factor_participacion / suma_participacion
                            potencia_inyectada_extra = -potencia_perdida * factor_gamma
                            flujo_post_falla += self.resultado_actual.matriz_gsf[k, self.mapa_indices_nodos[nodo_compensador.id]] * potencia_inyectada_extra
                self.riesgos_futuros_n_1[k] = max(self.riesgos_futuros_n_1[k], abs(flujo_post_falla))
                if linea_monitoreada.limite_potencia_mw > 0.0 and abs(flujo_post_falla) > linea_monitoreada.limite_potencia_mw:
                    conteo_vulnerabilidades += 1
                    mensaje = f"RIESGO DETECTADO: Si se dispara el Generador {nodo_gen.id}, la linea {linea_monitoreada.nodo_origen}-{linea_monitoreada.nodo_destino} subira a {abs(flujo_post_falla):.1f} MW."
                    self.lista_consola.addItem(mensaje)
        if conteo_vulnerabilidades == 0: 
            self.lista_consola.addItem("La red es completamente resistente ante cualquier evento unico (Criterio N-1 Satisfecho).")

    def calcular_flujo_dc_potencia(self, lineas_apagadas: Set[str], generadores_apagados: Set[int], cargas_apagadas: Set[int]) -> Optional[ResultadosSistema]:
        cantidad_nodos = len(self.lista_nodos)
        cantidad_lineas = len(self.lista_lineas)
        matriz_B = np.zeros((cantidad_nodos, cantidad_nodos))
        for linea in self.lista_lineas:
            nombre = f"{linea.nodo_origen}-{linea.nodo_destino}"
            if linea.activa and nombre not in lineas_apagadas:
                i = self.mapa_indices_nodos.get(linea.nodo_origen)
                j = self.mapa_indices_nodos.get(linea.nodo_destino)
                if i is not None and j is not None:
                    susceptancia_ij = 1.0 / linea.reactancia_pu
                    matriz_B[i, i] += susceptancia_ij
                    matriz_B[j, j] += susceptancia_ij
                    matriz_B[i, j] -= susceptancia_ij
                    matriz_B[j, i] -= susceptancia_ij
        try: 
            matriz_B_reducida = matriz_B[1:, 1:]
            matriz_F_reducida = np.linalg.inv(matriz_B_reducida)
        except np.linalg.LinAlgError: 
            return None 
        matriz_F = np.zeros((cantidad_nodos, cantidad_nodos))
        matriz_F[1:, 1:] = matriz_F_reducida
        vector_P = np.zeros(cantidad_nodos)
        potencia_gen_caida = sum(b.potencia_generada_mw for b in self.lista_nodos if b.generador_activo and b.id in generadores_apagados)
        suma_factores_participacion = sum(b.factor_participacion for b in self.lista_nodos if b.generador_activo and b.id not in generadores_apagados)
        for i, nodo in enumerate(self.lista_nodos):
            potencia_gen = 0.0
            if nodo.generador_activo and nodo.id not in generadores_apagados:
                potencia_gen = nodo.potencia_generada_mw
                if suma_factores_participacion > 0 and potencia_gen_caida > 0:
                    incremento_solicitado = potencia_gen_caida * (nodo.factor_participacion / suma_factores_participacion)
                    potencia_gen = min(nodo.potencia_maxima_mw, potencia_gen + incremento_solicitado)
            potencia_carga = 0.0 if (nodo.id in cargas_apagadas) else nodo.potencia_carga_mw
            vector_P[i] = (potencia_gen - potencia_carga) / POTENCIA_BASE_MVA
        vector_theta_radianes = matriz_F @ vector_P
        flujos_resultantes_mw =[]
        for linea in self.lista_lineas:
            i = self.mapa_indices_nodos.get(linea.nodo_origen)
            j = self.mapa_indices_nodos.get(linea.nodo_destino)
            if i is not None and j is not None:
                flujo_en_pu = (vector_theta_radianes[i] - vector_theta_radianes[j]) / linea.reactancia_pu
                nombre = f"{linea.nodo_origen}-{linea.nodo_destino}"
                if not linea.activa or nombre in lineas_apagadas:
                    flujos_resultantes_mw.append(0.0)
                else:
                    flujos_resultantes_mw.append(flujo_en_pu * POTENCIA_BASE_MVA)
            else: 
                flujos_resultantes_mw.append(0.0)
        matriz_GSF = np.zeros((cantidad_lineas, cantidad_nodos))
        for L, linea in enumerate(self.lista_lineas):
            nodo_envio = self.mapa_indices_nodos.get(linea.nodo_origen)
            nodo_recibo = self.mapa_indices_nodos.get(linea.nodo_destino)
            if nodo_envio is not None and nodo_recibo is not None:
                for i in range(cantidad_nodos):
                    matriz_GSF[L, i] = (matriz_F[nodo_envio, i] - matriz_F[nodo_recibo, i]) / linea.reactancia_pu
        matriz_LODF = np.zeros((cantidad_lineas, cantidad_lineas))
        for L, linea_saliente in enumerate(self.lista_lineas):
            idx_i = self.mapa_indices_nodos.get(linea_saliente.nodo_origen)
            idx_m = self.mapa_indices_nodos.get(linea_saliente.nodo_destino)
            if idx_i is not None and idx_m is not None:
                reactancia_L = linea_saliente.reactancia_pu
                denominador = reactancia_L - (matriz_F[idx_i, idx_i] + matriz_F[idx_m, idx_m] - 2.0 * matriz_F[idx_i, idx_m])
                if abs(denominador) > 1e-6:
                    for K, linea_observada in enumerate(self.lista_lineas):
                        if L == K: 
                            matriz_LODF[K, L] = -1.0
                            continue
                        idx_v = self.mapa_indices_nodos.get(linea_observada.nodo_origen)
                        idx_w = self.mapa_indices_nodos.get(linea_observada.nodo_destino)
                        if idx_v is not None and idx_w is not None:
                            numerador = (matriz_F[idx_v, idx_i] - matriz_F[idx_v, idx_m]) - (matriz_F[idx_w, idx_i] - matriz_F[idx_w, idx_m])
                            matriz_LODF[K, L] = (reactancia_L / linea_observada.reactancia_pu) * (numerador / denominador)
        return ResultadosSistema(
            matriz_b=matriz_B, 
            matriz_f=matriz_F, 
            matriz_gsf=matriz_GSF, 
            matriz_lodf=matriz_LODF, 
            flujos_mw=flujos_resultantes_mw, 
            angulos_radianes=vector_theta_radianes.tolist(), 
            topologia_valida=True
        )

    def algoritmo_wls_estimacion(self, base_res: ResultadosSistema) -> Tuple[List[float], List[float]]:
        cantidad_nodos = len(self.lista_nodos)
        cantidad_lineas = len(self.lista_lineas)
        vector_theta_real = np.array(base_res.angulos_radianes)
        vector_flujos_reales = np.array(base_res.flujos_mw)
        vector_inyecciones_reales = (base_res.matriz_b @ vector_theta_real)[1:] * POTENCIA_BASE_MVA
        np.random.seed(42)
        ruido_nodos = np.random.normal(0, 0.02 * np.mean(np.abs(vector_inyecciones_reales)) + 0.1, cantidad_nodos - 1)
        ruido_lineas = np.random.normal(0, 0.02 * np.mean(np.abs(vector_flujos_reales)) + 0.1, cantidad_lineas)
        vector_mediciones_Z = np.concatenate([vector_inyecciones_reales + ruido_nodos, vector_flujos_reales + ruido_lineas])
        H_nodos = base_res.matriz_b[1:, 1:] * POTENCIA_BASE_MVA
        H_lineas = np.zeros((cantidad_lineas, cantidad_nodos - 1))
        for idx_linea, linea in enumerate(self.lista_lineas):
            origen = self.mapa_indices_nodos.get(linea.nodo_origen)
            destino = self.mapa_indices_nodos.get(linea.nodo_destino)
            derivada = (1.0 / linea.reactancia_pu) * POTENCIA_BASE_MVA
            if origen is not None and origen > 0: H_lineas[idx_linea, origen - 1] = derivada
            if destino is not None and destino > 0: H_lineas[idx_linea, destino - 1] = -derivada
        Matriz_H = np.vstack([H_nodos, H_lineas])
        Matriz_R_inversa = np.diag(1.0 / np.concatenate([np.ones(cantidad_nodos-1)*4.0, np.ones(cantidad_lineas)*1.0]))
        try:
            H_trans_R_inv = Matriz_H.T @ Matriz_R_inversa
            theta_estimado = np.linalg.inv(H_trans_R_inv @ Matriz_H) @ H_trans_R_inv @ vector_mediciones_Z
            flujos_estimados_limpios = H_lineas @ theta_estimado
            return (vector_flujos_reales + ruido_lineas).tolist(), flujos_estimados_limpios.tolist()
        except:
            return (vector_flujos_reales + ruido_lineas).tolist(), vector_flujos_reales.tolist()

    def configurar_tabla_con_autoajuste(self, tabla_grafica: QTableWidget):
        tabla_grafica.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabla_grafica.verticalHeader().setVisible(False)

    def volcar_matriz_forzada(self, tabla_grafica: QTableWidget, matriz_datos: np.ndarray, etiquetas_h=None, etiquetas_v=None):
        filas, columnas = matriz_datos.shape
        tabla_grafica.clear()
        tabla_grafica.setRowCount(filas)
        tabla_grafica.setColumnCount(columnas)
        if etiquetas_h: 
            tabla_grafica.setHorizontalHeaderLabels(etiquetas_h)
            tabla_grafica.horizontalHeader().setVisible(True)
        else: 
            tabla_grafica.horizontalHeader().setVisible(False)
        if etiquetas_v: 
            tabla_grafica.setVerticalHeaderLabels(etiquetas_v)
            tabla_grafica.verticalHeader().setVisible(True)
        else: 
            tabla_grafica.verticalHeader().setVisible(False)
        tabla_grafica.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tabla_grafica.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tabla_grafica.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabla_grafica.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabla_grafica.horizontalHeader().setMinimumSectionSize(1)
        tabla_grafica.verticalHeader().setMinimumSectionSize(1)
        for i in range(filas):
            for j in range(columnas):
                valor = matriz_datos[i, j]
                celda = QTableWidgetItem(f"{valor:.3f}")
                celda.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                celda.setFont(QFont("Arial", 8))
                if abs(valor) < 0.0001: 
                    celda.setForeground(QColor("lightgray"))
                tabla_grafica.setItem(i, j, celda)

    def volcar_matriz_inteligente(self, tabla_grafica: QTableWidget, matriz_datos: np.ndarray, es_gsf: bool):
        etiquetas_h =[f"Nodo {n.id}" for n in self.lista_nodos] if es_gsf else[f"L {l.nodo_origen}-{l.nodo_destino}" for l in self.lista_lineas]
        etiquetas_v =[f"L {l.nodo_origen}-{l.nodo_destino}" for l in self.lista_lineas]
        filas, columnas = matriz_datos.shape
        tabla_grafica.clear()
        tabla_grafica.setRowCount(filas)
        tabla_grafica.setColumnCount(columnas)
        tabla_grafica.setHorizontalHeaderLabels(etiquetas_h)
        tabla_grafica.setVerticalHeaderLabels(etiquetas_v)
        tabla_grafica.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tabla_grafica.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tabla_grafica.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabla_grafica.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabla_grafica.horizontalHeader().setMinimumSectionSize(1)
        tabla_grafica.verticalHeader().setMinimumSectionSize(1)
        fuente_normal = QFont("Arial", 8)
        fuente_negrita = QFont("Arial", 8, QFont.Weight.Bold)
        for i in range(filas):
            linea_obj = self.lista_lineas[i]
            flujo_ahora = abs(self.resultado_actual.flujos_mw[i]) if self.resultado_actual else 0.0
            riesgo_futuro = self.riesgos_futuros_n_1[i] if i < len(self.riesgos_futuros_n_1) else 0.0
            en_peligro = linea_obj.limite_potencia_mw > 0.0 and ((flujo_ahora >= linea_obj.limite_potencia_mw) or (riesgo_futuro >= linea_obj.limite_potencia_mw))
            for j in range(columnas):
                valor = matriz_datos[i, j]
                celda = QTableWidgetItem(f"{valor:.3f}")
                celda.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                color_fondo, color_texto, tipo_fuente = QColor("white"), QColor("black"), fuente_normal
                if en_peligro:
                    color_fondo = QColor("#ffeeee")
                    umbral = 0.05 if es_gsf else 0.10
                    if abs(valor) > umbral:
                        color_fondo = QColor("#ffcccc")
                        color_texto = QColor("red")
                        tipo_fuente = fuente_negrita
                    else: 
                        color_texto = QColor("gray")
                else:
                    if abs(valor) < 0.001: 
                        color_texto = QColor("lightgray")
                celda.setBackground(color_fondo)
                celda.setForeground(color_texto)
                celda.setFont(tipo_fuente)
                tabla_grafica.setItem(i, j, celda)

    def actualizar_tablas_edicion(self):
        self.interfaz_bloqueada = True
        columnas_linea =["Origen", "Destino", "R(pu)", "X(pu)", "BCAP", "P0 Origen", "P0 Destino", "Limite MW", "Activa", "Accion"]
        self.tabla_lineas.setColumnCount(len(columnas_linea))
        self.tabla_lineas.setHorizontalHeaderLabels(columnas_linea)
        self.configurar_tabla_con_autoajuste(self.tabla_lineas)
        self.tabla_lineas.setRowCount(len(self.lista_lineas))
        for fila, linea in enumerate(self.lista_lineas):
            datos_mostrar =[linea.nodo_origen, linea.nodo_destino, linea.resistencia_pu, linea.reactancia_pu, linea.susceptancia_shunt_pu, linea.potencia_base_origen_mw, linea.potencia_base_destino_mw, linea.limite_potencia_mw]
            for col, valor in enumerate(datos_mostrar): 
                self.tabla_lineas.setItem(fila, col, QTableWidgetItem(str(valor)))
            caja_activa = QTableWidgetItem()
            caja_activa.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            caja_activa.setCheckState(Qt.CheckState.Checked if linea.activa else Qt.CheckState.Unchecked)
            self.tabla_lineas.setItem(fila, 8, caja_activa)
            boton_eliminar = QPushButton("Eliminar")
            boton_eliminar.clicked.connect(lambda _, fila_borrar=fila: self.evento_eliminar_linea(fila_borrar))
            self.tabla_lineas.setCellWidget(fila, 9, boton_eliminar)
        columnas_nodo =["Bus", "Tipo", "V(pu)", "P Gen(MW)", "P Max(MW)", "F.Part.", "P Carga(MW)", "Q Carga", "Activo", "Accion"]
        self.tabla_nodos.setColumnCount(len(columnas_nodo))
        self.tabla_nodos.setHorizontalHeaderLabels(columnas_nodo)
        self.configurar_tabla_con_autoajuste(self.tabla_nodos)
        self.tabla_nodos.setRowCount(len(self.lista_nodos))
        for fila, nodo in enumerate(self.lista_nodos):
            datos_mostrar =[nodo.id, nodo.tipo, nodo.voltaje_programado, nodo.potencia_generada_mw, nodo.potencia_maxima_mw, nodo.factor_participacion, nodo.potencia_carga_mw, nodo.potencia_reactiva_mvar]
            for col, valor in enumerate(datos_mostrar): 
                self.tabla_nodos.setItem(fila, col, QTableWidgetItem(str(valor)))
            caja_activa = QTableWidgetItem()
            caja_activa.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            caja_activa.setCheckState(Qt.CheckState.Checked if nodo.generador_activo else Qt.CheckState.Unchecked)
            self.tabla_nodos.setItem(fila, 8, caja_activa)
            boton_eliminar = QPushButton("Eliminar")
            boton_eliminar.clicked.connect(lambda _, fila_borrar=fila: self.evento_eliminar_nodo(fila_borrar))
            self.tabla_nodos.setCellWidget(fila, 9, boton_eliminar)
        self.interfaz_bloqueada = False

    def actualizar_pantalla_resultados(self):
        if not self.resultado_base or not self.resultado_actual: 
            return
        mensaje_semaforo = "Estado Seguro de Operacion Normal"
        self.etiqueta_estado_sistema.setStyleSheet("color: green;")
        if not self.resultado_actual.topologia_valida: 
            mensaje_semaforo = "ALERTA ROJA: Topologia no convergente (Posible Isla Electrica)."
            self.etiqueta_estado_sistema.setStyleSheet("color: red;")
        elif self.texto_comando_fallas.strip(): 
            mensaje_semaforo = "CONTINGENCIA ACTIVA. Revisar factores resaltados en rojo para acciones correctivas."
            self.etiqueta_estado_sistema.setStyleSheet("color: #d97706;")
        self.etiqueta_estado_sistema.setText(mensaje_semaforo)
        cabeceras_flujos =["Linea", "Base", "SCADA", "WLS", "Actual", "Limite Potencia", "Riesgo N-1"]
        self.tabla_flujos.setColumnCount(len(cabeceras_flujos))
        self.tabla_flujos.setHorizontalHeaderLabels(cabeceras_flujos)
        self.configurar_tabla_con_autoajuste(self.tabla_flujos)
        self.tabla_flujos.setRowCount(len(self.lista_lineas))
        for i, linea in enumerate(self.lista_lineas):
            if i >= len(self.resultado_base.flujos_mw): 
                continue
            self.tabla_flujos.setItem(i, 0, QTableWidgetItem(f"{linea.nodo_origen}-{linea.nodo_destino}"))
            self.tabla_flujos.setItem(i, 1, QTableWidgetItem(f"{self.resultado_base.flujos_mw[i]:.1f}"))
            val_scada = self.resultado_base.mediciones_scada_ruido[i] if self.resultado_base.mediciones_scada_ruido else 0.0
            val_wls = self.resultado_base.flujos_estimados_wls[i] if self.resultado_base.flujos_estimados_wls else 0.0
            self.tabla_flujos.setItem(i, 2, QTableWidgetItem(f"{val_scada:.1f}"))
            self.tabla_flujos.setItem(i, 3, QTableWidgetItem(f"{val_wls:.1f}"))
            flujo_hoy = self.resultado_actual.flujos_mw[i]
            esta_desconectada = not linea.activa or f"{linea.nodo_origen}-{linea.nodo_destino}" in self.texto_comando_fallas
            celda_actual = QTableWidgetItem("Desconectado" if esta_desconectada else f"{flujo_hoy:.1f}")
            if not esta_desconectada and linea.limite_potencia_mw > 0.0 and abs(flujo_hoy) > linea.limite_potencia_mw: 
                celda_actual.setForeground(QColor("orange"))
                celda_actual.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            if celda_actual.text() == "Desconectado": 
                celda_actual.setForeground(QColor("red"))
            self.tabla_flujos.setItem(i, 4, celda_actual)
            self.tabla_flujos.setItem(i, 5, QTableWidgetItem(f"{linea.limite_potencia_mw:.1f}"))
            riesgo_maximo = self.riesgos_futuros_n_1[i] if i < len(self.riesgos_futuros_n_1) else 0.0
            celda_riesgo = QTableWidgetItem(f"{riesgo_maximo:.1f}")
            if linea.limite_potencia_mw > 0.0 and riesgo_maximo > linea.limite_potencia_mw: 
                celda_riesgo.setForeground(QColor("red"))
                celda_riesgo.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.tabla_flujos.setItem(i, 6, celda_riesgo)
        lista_nombres_buses = [str(b.id) for b in self.lista_nodos]
        self.volcar_matriz_forzada(self.tabla_matriz_b, self.resultado_actual.matriz_b, lista_nombres_buses, lista_nombres_buses)
        self.volcar_matriz_forzada(self.tabla_matriz_f, self.resultado_actual.matriz_f, lista_nombres_buses, lista_nombres_buses)
        self.volcar_matriz_inteligente(self.tabla_gsf, self.resultado_actual.matriz_gsf, es_gsf=True)
        self.volcar_matriz_inteligente(self.tabla_lodf, self.resultado_actual.matriz_lodf, es_gsf=False)

    def evento_agregar_linea(self):
        self.lista_lineas.append(LineaTransmision(1, 2, 0.0, 0.1, 0.0, 0.0, 0.0, True, "1-2", 0.0))
        self.ejecutar_analisis_completo()

    def evento_agregar_nodo(self):
        id_nuevo = max([n.id for n in self.lista_nodos] + [0]) + 1
        self.lista_nodos.append(NodoElectrico(id_nuevo, "Load", 1.0, 0.0, 0.0, 0.0, True, 1000.0, 1.0))
        self.ejecutar_analisis_completo()

    def evento_eliminar_linea(self, indice): 
        if 0 <= indice < len(self.lista_lineas): 
            self.lista_lineas.pop(indice)
            self.ejecutar_analisis_completo()

    def evento_eliminar_nodo(self, indice): 
        if 0 <= indice < len(self.lista_nodos): 
            self.lista_nodos.pop(indice)
            self.ejecutar_analisis_completo()

    def evento_edicion_tabla_lineas(self, fila, columna):
        if self.interfaz_bloqueada: return
        try:
            texto = self.tabla_lineas.item(fila, columna).text()
            linea_editada = self.lista_lineas[fila]
            if columna == 0: linea_editada.nodo_origen = int(texto)
            elif columna == 1: linea_editada.nodo_destino = int(texto)
            elif columna == 2: linea_editada.resistencia_pu = float(texto)
            elif columna == 3: linea_editada.reactancia_pu = float(texto)
            elif columna == 4: linea_editada.susceptancia_shunt_pu = float(texto)
            elif columna == 5: linea_editada.potencia_base_origen_mw = float(texto)
            elif columna == 6: linea_editada.potencia_base_destino_mw = float(texto)
            elif columna == 7: linea_editada.limite_potencia_mw = float(texto)
            elif columna == 8: linea_editada.activa = (self.tabla_lineas.item(fila, 8).checkState() == Qt.CheckState.Checked)
            self.ejecutar_analisis_completo()
        except Exception: pass
        
    def evento_edicion_tabla_nodos(self, fila, columna):
        if self.interfaz_bloqueada: return
        try:
            texto = self.tabla_nodos.item(fila, columna).text()
            nodo_editado = self.lista_nodos[fila]
            if columna == 0: nodo_editado.id = int(texto)
            elif columna == 1: nodo_editado.tipo = texto
            elif columna == 2: nodo_editado.voltaje_programado = float(texto)
            elif columna == 3: nodo_editado.potencia_generada_mw = float(texto)
            elif columna == 4: nodo_editado.potencia_maxima_mw = float(texto)
            elif columna == 5: nodo_editado.factor_participacion = float(texto)
            elif columna == 6: nodo_editado.potencia_carga_mw = float(texto)
            elif columna == 7: nodo_editado.potencia_reactiva_mvar = float(texto)
            elif columna == 8: nodo_editado.generador_activo = (self.tabla_nodos.item(fila, 8).checkState() == Qt.CheckState.Checked)
            self.ejecutar_analisis_completo()
        except Exception: pass

if __name__ == "__main__":
    aplicacion_qt = QApplication(sys.argv)
    aplicacion_qt.setStyle('Fusion')
    ventana_principal = VentanaCentroControl()
    ventana_principal.show()
    sys.exit(aplicacion_qt.exec())