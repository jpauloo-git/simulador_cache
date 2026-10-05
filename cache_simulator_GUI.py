import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.patches import FancyBboxPatch

import random
import math
import time
import sys
import os
from datetime import datetime
from abc import ABC, abstractmethod
from typing import List, Tuple
import customtkinter as ctk

# Configuração visual inicial do CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Guardar stdout original para restauração no fechamento
ORIGINAL_STDOUT = sys.stdout

# ==============================================================================
# 1. CORE DO SIMULADOR
# ==============================================================================

class CacheLine:
    def __init__(self):
        self.valid_bit: bool = False
        self.dirty_bit: bool = False
        self.tag: int = -1
        self.insertion_time: int = 0
        self.last_access_time: int = 0
        self.access_frequency: int = 0

    def update_access_metadata(self, current_time: int) -> None:
        self.last_access_time = current_time
        self.access_frequency += 1


class EvictionPolicy(ABC):
    @abstractmethod
    def find_victim(self, lines: List[CacheLine]) -> CacheLine:
        pass


class FIFO(EvictionPolicy):
    def find_victim(self, lines: List[CacheLine]) -> CacheLine:
        return min(lines, key=lambda line: line.insertion_time)


class LRU(EvictionPolicy):
    def find_victim(self, lines: List[CacheLine]) -> CacheLine:
        return min(lines, key=lambda line: line.last_access_time)


class LFU(EvictionPolicy):
    def find_victim(self, lines: List[CacheLine]) -> CacheLine:
        return min(lines, key=lambda line: (line.access_frequency, line.last_access_time))


class RandomPolicy(EvictionPolicy):
    def find_victim(self, lines: List[CacheLine]) -> CacheLine:
        return random.choice(lines)


class CacheSet:
    def __init__(self, associativity: int, policy: EvictionPolicy):
        self.ways = associativity
        self.lines: List[CacheLine] = [CacheLine() for _ in range(associativity)]
        self.policy: EvictionPolicy = policy

    def access(self, tag: int, current_time: int) -> bool:
        for line in self.lines:
            if line.valid_bit and line.tag == tag:
                line.update_access_metadata(current_time)
                return True

        for line in self.lines:
            if not line.valid_bit:
                self._insert_block(line, tag, current_time)
                return False

        victim_line = self.policy.find_victim(self.lines)
        self._insert_block(victim_line, tag, current_time)
        return False

    def _insert_block(self, line: CacheLine, tag: int, current_time: int) -> None:
        line.valid_bit = True
        line.tag = tag
        line.insertion_time = current_time
        line.last_access_time = current_time
        line.access_frequency = 1
        line.dirty_bit = False


class CacheMemory:
    def __init__(self, cache_size_bytes: int, block_size_bytes: int, associativity: int, policy_name: str):
        self.cache_size = cache_size_bytes
        self.block_size = block_size_bytes
        self.associativity = associativity
        
        self.num_blocks = self.cache_size // self.block_size
        self.num_sets = self.num_blocks // self.associativity
        
        self.offset_bits = int(math.log2(self.block_size))
        self.index_bits = int(math.log2(self.num_sets))
        
        policy_map = {"FIFO": FIFO(), "LRU": LRU(), "LFU": LFU(), "Random": RandomPolicy()}
        self.policy = policy_map.get(policy_name, FIFO())

        self.sets: List[CacheSet] = [CacheSet(self.associativity, self.policy) for _ in range(self.num_sets)]
        
        self.global_clock: int = 0
        self.hits: int = 0
        self.misses: int = 0

    def calculate_address_fields(self, address: int) -> Tuple[int, int, int]:
        offset_mask = (1 << self.offset_bits) - 1
        offset = address & offset_mask
        
        index_mask = (1 << self.index_bits) - 1
        index = (address >> self.offset_bits) & index_mask
        
        tag = address >> (self.offset_bits + self.index_bits)
        return tag, index, offset

    def request_access(self, address: int) -> bool:
        self.global_clock += 1
        tag, index, _ = self.calculate_address_fields(address)
        hit = self.sets[index].access(tag, self.global_clock)
        if hit:
            self.hits += 1
        else:
            self.misses += 1
        return hit

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

# ==============================================================================
# 2. MOTOR DE SIMULAÇÃO E UTILITÁRIOS
# ==============================================================================

def is_power_of_two(x: int) -> bool:
    return (x != 0) and ((x & (x - 1)) == 0)

def gerar_padrao_realista(acessos: int, memory_size: int, regioes_quentes: List[int], probs: Tuple[float, float, float]) -> List[int]:
    prob_temporal, prob_espacial, prob_quente = probs
    padrao = []
    endereco_anterior = random.randint(0, memory_size - 1)
    
    for _ in range(acessos):
        r = random.random()
        if r < prob_temporal:
            endereco = endereco_anterior
        elif r < prob_temporal + prob_espacial:
            deslocamento = random.randint(-16, 16)
            endereco = max(0, min(memory_size - 1, endereco_anterior + deslocamento))
        elif r < prob_temporal + prob_espacial + prob_quente:
            base = random.choice(regioes_quentes)
            deslocamento = random.randint(0, 3)
            endereco = min(memory_size - 1, base + deslocamento)
        else:
            endereco = random.randint(0, memory_size - 1)

        padrao.append(endereco)
        endereco_anterior = endereco

    return padrao

def simulacao_monte_carlo(n_simulacoes: int, acessos: int, memory_size: int, cache_size: int,
                          associatividade: int, regioes_quentes: List[int], probs: Tuple[float, float, float],
                          bloco_tamanho: int, algoritmo: str) -> float:
    taxas_acerto = []

    for _ in range(n_simulacoes):
        padrao = gerar_padrao_realista(acessos, memory_size, regioes_quentes, probs)
        cache = CacheMemory(cache_size, bloco_tamanho, associatividade, algoritmo)
        for endereco in padrao:
            cache.request_access(endereco)
        taxas_acerto.append(cache.hit_rate)

    print(f"--- Bloco: {bloco_tamanho} Bytes | Hit Rate Médio: {np.mean(taxas_acerto):.4f} | Std: {np.std(taxas_acerto):.4f} ---")
    return float(np.mean(taxas_acerto))

class CustomTkRedirector:
    def __init__(self, textbox: ctk.CTkTextbox):
        self.textbox = textbox

    def write(self, text: str):
        try:
            if self.textbox.winfo_exists():
                self.textbox.configure(state="normal")
                self.textbox.insert("end", text)
                self.textbox.see("end")
                self.textbox.configure(state="disabled")
        except Exception:
            pass

    def flush(self):
        pass

class StyledNavigationToolbar(NavigationToolbar2Tk):
    def __init__(self, canvas, parent):
        super().__init__(canvas, parent)
        self.config(background='#1e1e2e')
        for button in self.winfo_children():
            button.config(background='#1e1e2e')

# ==============================================================================
# 3. INTERFACE GRÁFICA MODERNA
# ==============================================================================

class CacheSimulatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Cache Memory Simulator - Executive Dashboard")
        self.geometry("1280x800")
        self.minsize(1100, 700)

        self.algoritmo_escolhido = "FIFO"
        self.resultados = []
        self.plot_lines = []
        self.is_running = True

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self._build_layout()
        sys.stdout = CustomTkRedirector(self.textbox_console)

    def on_closing(self):
        self.is_running = False
        sys.stdout = ORIGINAL_STDOUT
        plt.close('all')
        self.quit()
        self.destroy()

    def _build_layout(self):
        # Header
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(15, 5))

        self.lbl_title = ctk.CTkLabel(
            self.header_frame, text=" SIMULADOR DE MEMÓRIA CACHE", 
            font=ctk.CTkFont(size=20, weight="bold"), text_color="#00c8ff"
        )
        self.lbl_title.pack(side="left")

        self.lbl_subtitle = ctk.CTkLabel(
            self.header_frame, text=" | Dashboard de Arquitetura de Computadores", 
            font=ctk.CTkFont(size=14), text_color="#a0a0a0"
        )
        self.lbl_subtitle.pack(side="left", padx=5)

        # Container Principal
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=10)

        # SIDEBAR DE CONFIGURAÇÃO
        self.sidebar = ctk.CTkScrollableFrame(self.main_container, width=350, corner_radius=10)
        self.sidebar.pack(side="left", fill="y", padx=(0, 15))

        lbl_config = ctk.CTkLabel(self.sidebar, text=" Configuração da Cache", font=ctk.CTkFont(size=16, weight="bold"), text_color="#00c8ff")
        lbl_config.pack(anchor="w", pady=(5, 10))

        # Hardware
        ctk.CTkLabel(self.sidebar, text="Parâmetros do Hardware", font=ctk.CTkFont(size=12, weight="bold"), text_color="#a0a0a0").pack(anchor="w", pady=(5, 2))
        
        self.entry_ram = self._add_stepper_field(self.sidebar, "RAM (Bytes):", "1048576", is_pow2=True)
        self.entry_cache = self._add_stepper_field(self.sidebar, "Tamanho Cache:", "8192", is_pow2=True)
        self.entry_assoc = self._add_stepper_field(self.sidebar, "Associatividade:", "16", is_pow2=True)

        ctk.CTkLabel(self.sidebar, text="Algoritmo de Substituição:", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(5, 2))
        self.combo_algo = ctk.CTkComboBox(self.sidebar, values=["FIFO", "LRU", "LFU", "Random"], command=self._selecionar_algoritmo)
        self.combo_algo.set("FIFO")
        self.combo_algo.pack(fill="x", pady=(0, 10))

        # Padrão de Carga
        ctk.CTkLabel(self.sidebar, text="Padrão de Acesso & Carga", font=ctk.CTkFont(size=12, weight="bold"), text_color="#a0a0a0").pack(anchor="w", pady=(10, 2))
        
        self.entry_acessos = self._add_stepper_field(self.sidebar, "Acessos CPU:", "10000", step=1000)
        self.entry_sims = self._add_stepper_field(self.sidebar, "Simulações MC:", "10", step=1)
        self.entry_prob_temp = self._add_stepper_field(self.sidebar, "Prob. Temporal:", "0.20", step=0.05, is_float=True)
        self.entry_prob_esp = self._add_stepper_field(self.sidebar, "Prob. Espacial:", "0.20", step=0.05, is_float=True)
        self.entry_prob_hot = self._add_stepper_field(self.sidebar, "Prob. Hot Regions:", "0.40", step=0.05, is_float=True)

        # Blocos Analisados (Container Dinâmico)
        self.lbl_blocos_title = ctk.CTkLabel(self.sidebar, text="Blocos Analisados (Bytes):", font=ctk.CTkFont(size=12, weight="bold"), text_color="#a0a0a0")
        self.lbl_blocos_title.pack(anchor="w", pady=(10, 2))

        self.frame_blocos_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_blocos_container.pack(fill="x", pady=(0, 15))

        # Entrada para simulações (Lista de valores)
        self.entry_blocos_multi = ctk.CTkEntry(self.frame_blocos_container)
        self.entry_blocos_multi.insert(0, "2,4,8,16,32,64,128,256,512")
        self.entry_blocos_multi.pack(fill="x")

        # Entrada para o Diagrama em Blocos (Valor único com Stepper '+' e '-')
        self.frame_bloco_single = ctk.CTkFrame(self.frame_blocos_container, fg_color="transparent")
        self.entry_bloco_single = self._add_stepper_field(self.frame_bloco_single, "Tamanho:", "2", is_pow2=True)

        # Botões de Ação
        self.btn_run = ctk.CTkButton(self.sidebar, text=" Executar Simulação", fg_color="#0072ce", hover_color="#008cff", height=38, font=ctk.CTkFont(weight="bold"), command=self.rodar_simulacao_callback)
        self.btn_run.pack(fill="x", pady=5)

        btn_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_row.pack(fill="x", pady=5)
        
        self.btn_clear_last = ctk.CTkButton(btn_row, text="Limpar Último", fg_color="#3a3d4a", hover_color="#4d5162", width=160, command=self.limpar_ultimo_plot)
        self.btn_clear_last.pack(side="left", padx=(0, 5))

        self.btn_reset = ctk.CTkButton(btn_row, text="Reset Total", fg_color="#3a3d4a", hover_color="#4d5162", width=160, command=self.limpar_plots)
        self.btn_reset.pack(side="right")

        self.progressbar = ctk.CTkProgressBar(self.sidebar)
        self.progressbar.set(0.0)
        self.progressbar.pack(fill="x", pady=(15, 5))

        self.lbl_msg_erro = ctk.CTkLabel(self.sidebar, text="", text_color="#ff5050", wraplength=310)
        self.lbl_msg_erro.pack(fill="x", pady=5)

        # DASHBOARD PRINCIPAL
        self.dashboard = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.dashboard.pack(side="right", fill="both", expand=True)

        # CARDS KPI
        self.kpi_frame = ctk.CTkFrame(self.dashboard, fg_color="transparent")
        self.kpi_frame.pack(fill="x", pady=(0, 10))

        self.card_algo = self._create_kpi_card(self.kpi_frame, "ALGORITMO ATIVO", "Algoritmo: FIFO", "#00d2ff")
        self.card_algo.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.card_hit = self._create_kpi_card(self.kpi_frame, "DESEMPENHO MÁXIMO", "Hit Rate Máx: --%", "#00ff96")
        self.card_hit.pack(side="left", fill="x", expand=True, padx=5)

        self.card_status = self._create_kpi_card(self.kpi_frame, "STATUS DO SISTEMA", "Status: Aguardando", "#f0c850")
        self.card_status.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # ABAS
        self.tabview = ctk.CTkTabview(self.dashboard, command=self.on_tab_change)
        self.tabview.pack(fill="both", expand=True)

        self.tab_plot = self.tabview.add(" Curva de Desempenho (Hit Rate)")
        self.tab_console = self.tabview.add(" Console Serial & Dados")
        self.tab_heatmap = self.tabview.add(" Ferramentas Visuais (Heatmap)")
        self.tab_diagram = self.tabview.add(" Diagrama em Blocos")

        self._setup_tab_plot()
        self._setup_tab_console()
        self._setup_tab_heatmap()
        self._setup_tab_diagram()

    def on_tab_change(self):
        """Alterna o campo de entrada do tamanho do bloco dependendo da aba ativa."""
        tab_ativa = self.tabview.get()
        if tab_ativa == " Diagrama em Blocos":
            self.lbl_blocos_title.configure(text="Tamanho do Bloco (Bytes):")
            self.entry_blocos_multi.pack_forget()
            self.frame_bloco_single.pack(fill="x")
            self.desenhar_diagrama_blocos()
        else:
            self.lbl_blocos_title.configure(text="Blocos Analisados (Bytes):")
            self.frame_bloco_single.pack_forget()
            self.entry_blocos_multi.pack(fill="x")

    def _add_stepper_field(self, parent, label_text, default_val, step=1, is_float=False, is_pow2=False):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=3)

        lbl = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=12))
        lbl.pack(side="left")

        controls_frame = ctk.CTkFrame(frame, fg_color="transparent")
        controls_frame.pack(side="right")

        entry = ctk.CTkEntry(controls_frame, width=80, justify="center")
        entry.insert(0, str(default_val))
        entry.bind("<KeyRelease>", lambda e: self.desenhar_diagrama_blocos())

        def adjust(direction):
            try:
                if is_pow2:
                    val = int(entry.get())
                    new_val = val * 2 if direction > 0 else max(1, val // 2)
                    entry.delete(0, "end")
                    entry.insert(0, str(new_val))
                elif is_float:
                    val = float(entry.get()) + (step * direction)
                    entry.delete(0, "end")
                    entry.insert(0, f"{max(0.0, min(1.0, val)):.2f}")
                else:
                    val = int(entry.get()) + (step * direction)
                    entry.delete(0, "end")
                    entry.insert(0, str(max(1, val)))
                
                # Atualiza o diagrama dinamicamente ao alterar parâmetros
                self.desenhar_diagrama_blocos()
            except ValueError:
                pass

        btn_minus = ctk.CTkButton(
            controls_frame, text="-", width=26, height=26, fg_color="#3a3d4a", 
            hover_color="#0072ce", font=ctk.CTkFont(size=14, weight="bold"), 
            command=lambda: adjust(-1)
        )
        btn_plus = ctk.CTkButton(
            controls_frame, text="+", width=26, height=26, fg_color="#3a3d4a", 
            hover_color="#0072ce", font=ctk.CTkFont(size=14, weight="bold"), 
            command=lambda: adjust(1)
        )

        btn_minus.pack(side="left", padx=(0, 2))
        entry.pack(side="left", padx=2)
        btn_plus.pack(side="left", padx=(2, 0))

        return entry

    def _create_kpi_card(self, parent, title, initial_val, color):
        card = ctk.CTkFrame(parent, corner_radius=8)
        lbl_t = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=10, weight="bold"), text_color="#808080")
        lbl_t.pack(anchor="w", padx=12, pady=(8, 0))
        lbl_v = ctk.CTkLabel(card, text=initial_val, font=ctk.CTkFont(size=14, weight="bold"), text_color=color)
        lbl_v.pack(anchor="w", padx=12, pady=(0, 8))
        card.label_val = lbl_v
        return card

    def _setup_tab_plot(self):
        self.fig_plot, self.ax_plot = plt.subplots(figsize=(8, 4.5), dpi=100)
        self._setup_ax_plot_style()

        self.canvas_plot = FigureCanvasTkAgg(self.fig_plot, master=self.tab_plot)
        self.canvas_plot.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=(5, 0))

        self.toolbar_plot = StyledNavigationToolbar(self.canvas_plot, self.tab_plot)
        self.toolbar_plot.update()

    def _setup_ax_plot_style(self):
        self.fig_plot.patch.set_facecolor('#1e1e2e')
        self.ax_plot.set_facecolor('#1e1e2e')
        self.ax_plot.tick_params(colors='white')
        self.ax_plot.xaxis.label.set_color('white')
        self.ax_plot.yaxis.label.set_color('white')
        self.ax_plot.title.set_color('#00c8ff')
        for spine in self.ax_plot.spines.values():
            spine.set_color('#333d52')
        self.ax_plot.set_xlabel("Tamanho do Bloco (log2 Bytes)")
        self.ax_plot.set_ylabel("Taxa de Acerto (Hit Rate)")
        self.ax_plot.set_title("Taxa de Acerto vs Tamanho do Bloco (Escala Log2)")
        self.ax_plot.grid(True, linestyle='--', alpha=0.2, color='#ffffff')

    def _setup_tab_console(self):
        lbl1 = ctk.CTkLabel(self.tab_console, text="Saída do Console da CPU / Logs em Tempo Real:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#a0a0a0")
        lbl1.pack(anchor="w", padx=5, pady=(5, 2))

        self.textbox_console = ctk.CTkTextbox(self.tab_console, height=220, font=ctk.CTkFont(family="Consolas", size=11))
        self.textbox_console.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        lbl2 = ctk.CTkLabel(self.tab_console, text="Matriz de Exportação Rápidas (Arrays/CSV):", font=ctk.CTkFont(size=12, weight="bold"), text_color="#a0a0a0")
        lbl2.pack(anchor="w", padx=5, pady=(5, 2))

        self.textbox_resultados = ctk.CTkTextbox(self.tab_console, height=120, font=ctk.CTkFont(family="Consolas", size=11))
        self.textbox_resultados.pack(fill="both", expand=True, padx=5, pady=(0, 5))

    def _setup_tab_heatmap(self):
        ctrl_frame = ctk.CTkFrame(self.tab_heatmap, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=5, pady=5)

        lbl = ctk.CTkLabel(ctrl_frame, text=" Visualização Espacial da Localidade de Acesso\nO Mapa de Calor exibe como os endereços de memória são requisitados ao longo do tempo.", font=ctk.CTkFont(size=12), text_color="#a0a0a0", justify="left")
        lbl.pack(side="left", padx=5)

        btn_generate = ctk.CTkButton(ctrl_frame, text="Gerar / Atualizar Heatmap", fg_color="#0072ce", hover_color="#008cff", command=self.exibir_mapa_temporal_blocos)
        btn_generate.pack(side="right", padx=5)

        btn_clear = ctk.CTkButton(ctrl_frame, text="Limpar Heatmap", fg_color="#3a3d4a", hover_color="#4d5162", command=self.limpar_mapa_calor)
        btn_clear.pack(side="right", padx=5)

        self.fig_heatmap, self.ax_heatmap = plt.subplots(figsize=(8, 4), dpi=100)
        self.fig_heatmap.patch.set_facecolor('#1e1e2e')
        self.ax_heatmap.set_facecolor('#1e1e2e')
        self.ax_heatmap.axis('off')

        self.canvas_heatmap = FigureCanvasTkAgg(self.fig_heatmap, master=self.tab_heatmap)
        self.canvas_heatmap.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=(5, 0))

        self.toolbar_heatmap = StyledNavigationToolbar(self.canvas_heatmap, self.tab_heatmap)
        self.toolbar_heatmap.update()

    def _setup_tab_diagram(self):
        """Configura a aba com o diagrama em blocos do sistema."""
        ctrl_frame = ctk.CTkFrame(self.tab_diagram, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=5, pady=5)

        lbl = ctk.CTkLabel(
            ctrl_frame, 
            text=" Diagrama Arquitetural do Sistema\nExibe a decomposição do barramento e a organização da Cache (Conjuntos/Vias) em tempo real.",
            font=ctk.CTkFont(size=12), text_color="#a0a0a0", justify="left"
        )
        lbl.pack(side="left", padx=5)

        btn_generate = ctk.CTkButton(
            ctrl_frame, text="Atualizar Diagrama", fg_color="#0072ce", 
            hover_color="#008cff", command=self.desenhar_diagrama_blocos
        )
        btn_generate.pack(side="right", padx=5)

        self.fig_diagram, self.ax_diagram = plt.subplots(figsize=(8, 4.5), dpi=100)
        self.fig_diagram.patch.set_facecolor('#1e1e2e')
        self.ax_diagram.set_facecolor('#1e1e2e')
        self.ax_diagram.axis('off')

        self.canvas_diagram = FigureCanvasTkAgg(self.fig_diagram, master=self.tab_diagram)
        self.canvas_diagram.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=(5, 0))

        self.toolbar_diagram = StyledNavigationToolbar(self.canvas_diagram, self.tab_diagram)
        self.toolbar_diagram.update()

        self.desenhar_diagrama_blocos()

    # --------------------------------------------------------------------------
    # DESENHO DINÂMICO DO DIAGRAMA DE BLOCOS
    # --------------------------------------------------------------------------
    def desenhar_diagrama_blocos(self):
        if not self.is_running:
            return

        self.fig_diagram.clear()
        ax = self.fig_diagram.add_subplot(111)
        ax.set_facecolor('#1e1e2e')
        ax.axis('off')
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 6)

        try:
            memory_size = int(self.entry_ram.get())
            cache_size = int(self.entry_cache.get())
            associatividade = int(self.entry_assoc.get())
            bloco_tamanho = int(self.entry_bloco_single.get())
        except Exception:
            memory_size = 1048576
            cache_size = 8192
            associatividade = 16
            bloco_tamanho = 2

        if memory_size <= 0 or cache_size <= 0 or associatividade <= 0 or bloco_tamanho <= 0:
            ax.text(5, 3, "Parâmetros inválidos para renderizar o diagrama.", color="#ff5050", fontsize=12, ha='center')
            self.canvas_diagram.draw()
            return

        num_blocks = cache_size // bloco_tamanho
        num_sets = num_blocks // associatividade if associatividade > 0 else 0

        if num_sets < 1:
            ax.text(5, 3, " Configuração Inválida:\nNúmero de Conjuntos < 1\n(Aumente a Cache ou Reduza o Bloco/Associatividade)", color="#ff5050", fontsize=12, ha='center', va='center')
            self.canvas_diagram.draw()
            return

        addr_bits = int(math.log2(memory_size)) if memory_size > 0 else 0
        offset_bits = int(math.log2(bloco_tamanho)) if bloco_tamanho > 0 else 0
        index_bits = int(math.log2(num_sets)) if num_sets > 0 else 0
        tag_bits = addr_bits - index_bits - offset_bits

        if tag_bits < 0:
            ax.text(5, 3, " Configuração Inválida: Tag Bits < 0", color="#ff5050", fontsize=12, ha='center')
            self.canvas_diagram.draw()
            return

        # 1. MICROPROCESSADOR (CPU)
        box_cpu = FancyBboxPatch((0.4, 1.0), 2.4, 4.2, boxstyle="round,pad=0.1,rounding_size=0.2", ec="#00c8ff", fc="#252736", lw=2)
        ax.add_patch(box_cpu)
        ax.text(1.6, 4.8, "CPU\n(Processador)", color="#00c8ff", fontsize=11, fontweight='bold', ha='center', va='center')
        ax.text(1.6, 3.8, f"Endereço: {addr_bits} bits", color="white", fontsize=9, ha='center')
        ax.text(1.6, 3.2, f"Endereço (Bloco {bloco_tamanho}B):", color="#a0a0a0", fontsize=8, ha='center')

        box_addr = FancyBboxPatch((0.6, 1.3), 2.0, 1.5, boxstyle="square,pad=0.05", ec="#4d5162", fc="#1a1b26", lw=1)
        ax.add_patch(box_addr)
        ax.text(1.6, 2.5, "Divisão do Endereço", color="#00c8ff", fontsize=8, fontweight='bold', ha='center')
        ax.text(1.6, 2.1, f"TAG: {tag_bits} bits", color="#ff9d00", fontsize=8, ha='center')
        ax.text(1.6, 1.8, f"INDEX: {index_bits} bits", color="#00ff96", fontsize=8, ha='center')
        ax.text(1.6, 1.5, f"OFFSET: {offset_bits} bits", color="#ff5050", fontsize=8, ha='center')

        # 2. MEMÓRIA CACHE
        box_cache = FancyBboxPatch((3.7, 0.6), 3.0, 4.8, boxstyle="round,pad=0.1,rounding_size=0.2", ec="#00ff96", fc="#252736", lw=2)
        ax.add_patch(box_cache)
        ax.text(5.2, 5.0, "MEMÓRIA CACHE", color="#00ff96", fontsize=11, fontweight='bold', ha='center', va='center')
        
        cache_kb = cache_size / 1024
        cache_str = f"{cache_kb:.1f} KB" if cache_kb >= 1 else f"{cache_size} B"
        ax.text(5.2, 4.6, f"Tamanho: {cache_str} | {num_blocks} Blocos", color="white", fontsize=8, ha='center')
        
        if associatividade == 1:
            org_str = "Mapeamento Direto (1-way)"
        elif associatividade == num_blocks:
            org_str = "Totalmente Associativo"
        else:
            org_str = f"Conjunto-Associativo ({associatividade}-way)"
        
        ax.text(5.2, 4.3, org_str, color="#00c8ff", fontsize=8, fontweight='bold', ha='center')
        ax.text(5.2, 4.0, f"Total de Conjuntos: {num_sets}", color="#a0a0a0", fontsize=8, ha='center')

        # Representação gráfica dos Conjuntos e Vias
        y_start = 3.3
        display_sets = min(num_sets, 4)
        set_height = 0.5
        for i in range(display_sets):
            y_pos = y_start - i * (set_height + 0.15)
            set_label = f"Conj. {i}" if i < display_sets - 1 or num_sets <= 4 else f"Conj. {num_sets-1}"
            
            box_set = FancyBboxPatch((3.9, y_pos), 2.6, set_height, boxstyle="square,pad=0.02", ec="#00ff96", fc="#1a1b26", lw=1)
            ax.add_patch(box_set)
            ax.text(4.0, y_pos + 0.25, set_label, color="#00ff96", fontsize=7, fontweight='bold', va='center')

            display_ways = min(associatividade, 4)
            way_width = 1.8 / display_ways
            for w in range(display_ways):
                x_way = 4.6 + w * way_width
                box_way = FancyBboxPatch((x_way, y_pos + 0.08), way_width - 0.03, set_height - 0.16, boxstyle="square,pad=0.01", ec="#4d5162", fc="#2d3142", lw=0.8)
                ax.add_patch(box_way)
                way_text = f"Via {w}" if w < display_ways - 1 or associatividade <= 4 else f"Via {associatividade-1}"
                ax.text(x_way + way_width/2 - 0.015, y_pos + 0.25, way_text, color="white", fontsize=6, ha='center', va='center')

        if num_sets > 4:
            ax.text(5.2, y_start - 2.25, "... [Conjuntos Intermediários Omitidos] ...", color="#808080", fontsize=7, ha='center')

        # 3. MEMÓRIA RAM
        box_ram = FancyBboxPatch((7.4, 1.0), 2.2, 4.2, boxstyle="round,pad=0.1,rounding_size=0.2", ec="#ff9d00", fc="#252736", lw=2)
        ax.add_patch(box_ram)
        ax.text(8.5, 4.8, "MEMÓRIA RAM", color="#ff9d00", fontsize=11, fontweight='bold', ha='center', va='center')
        
        ram_mb = memory_size / (1024 * 1024)
        ram_str = f"{ram_mb:.1f} MB" if ram_mb >= 1 else f"{memory_size // 1024} KB"
        ax.text(8.5, 4.4, f"Tamanho: {ram_str}", color="white", fontsize=8, ha='center')
        total_ram_blocks = memory_size // bloco_tamanho
        ax.text(8.5, 4.1, f"Total: {total_ram_blocks} blocos", color="#a0a0a0", fontsize=8, ha='center')

        y_ram = 3.3
        for b_idx in range(4):
            y_p = y_ram - b_idx * 0.55
            b_label = f"Bloco {b_idx}" if b_idx < 3 else f"Bloco {total_ram_blocks-1}"
            if b_idx == 2 and total_ram_blocks > 4:
                b_label = "..."
            box_b = FancyBboxPatch((7.6, y_p), 1.8, 0.45, boxstyle="square,pad=0.02", ec="#ff9d00", fc="#1a1b26", lw=1)
            ax.add_patch(box_b)
            ax.text(8.5, y_p + 0.22, b_label, color="white", fontsize=7, ha='center', va='center')

        # INTERCONEXÕES E BARRAMENTOS
        ax.annotate("", xy=(3.7, 3.2), xytext=(2.8, 3.2), arrowprops=dict(arrowstyle="->", color="#00c8ff", lw=1.8))
        ax.text(3.25, 3.35, "Endereço\n(Index/Tag)", color="#00c8ff", fontsize=7, ha='center', fontweight='bold')

        ax.annotate("", xy=(2.8, 1.8), xytext=(3.7, 1.8), arrowprops=dict(arrowstyle="->", color="#00ff96", lw=1.8))
        ax.text(3.25, 1.95, "Dado (Hit)", color="#00ff96", fontsize=7, ha='center', fontweight='bold')

        ax.annotate("", xy=(7.4, 2.6), xytext=(6.7, 2.6), arrowprops=dict(arrowstyle="<->", color="#ff9d00", lw=1.8))
        ax.text(7.05, 2.8, "Bloco (Miss)", color="#ff9d00", fontsize=7, ha='center', fontweight='bold')

        self.fig_diagram.tight_layout()
        self.canvas_diagram.draw()

    # --------------------------------------------------------------------------
    # EVENTOS E SIMULAÇÃO
    # --------------------------------------------------------------------------
    def _selecionar_algoritmo(self, choice):
        self.algoritmo_escolhido = choice
        self.card_algo.label_val.configure(text=f"Algoritmo: {self.algoritmo_escolhido}")

    def rodar_simulacao_callback(self):
        start_time = time.time()
        self.lbl_msg_erro.configure(text="")
        self.card_status.label_val.configure(text="Status: Executando...")
        self.update_idletasks()

        try:
            memory_size = int(self.entry_ram.get())
            acessos = int(self.entry_acessos.get())
            tamanho_cache_bytes = int(self.entry_cache.get())
            associatividade = int(self.entry_assoc.get())
            n_simulacoes = int(self.entry_sims.get())
            prob_temporal = float(self.entry_prob_temp.get())
            prob_espacial = float(self.entry_prob_esp.get())
            prob_quente = float(self.entry_prob_hot.get())
            blocos_raw = self.entry_blocos_multi.get()
            blocos = [int(b.strip()) for b in blocos_raw.split(",")]

            regioes_quentes = [64, 1024, 8192, 32768, 131072, 262144, 524288, 786432, 983040]

            if not (2**20 <= memory_size <= 2**30) or not is_power_of_two(memory_size):
                self.lbl_msg_erro.configure(text="[ERRO] Memory Size deve ser potência de 2 entre 2^20 e 2^30.")
                self.card_status.label_val.configure(text="Status: Erro de Entrada")
                return

            if not is_power_of_two(associatividade):
                self.lbl_msg_erro.configure(text="[ERRO] Associatividade deve ser potência de 2.")
                self.card_status.label_val.configure(text="Status: Erro de Entrada")
                return

            if not is_power_of_two(tamanho_cache_bytes) or tamanho_cache_bytes >= memory_size:
                self.lbl_msg_erro.configure(text="[ERRO] Cache deve ser potência de 2 e menor que a RAM.")
                self.card_status.label_val.configure(text="Status: Erro de Entrada")
                return

            self.resultados.clear()
            contador_barra = 0
            self.progressbar.set(0.01)
            self.update_idletasks()

            for bt in blocos:
                if not self.is_running:
                    return

                if bt <= 0 or not is_power_of_two(bt):
                    self.lbl_msg_erro.configure(text=f"[ERRO] Bloco {bt} inválido. Use potências de 2.")
                    self.card_status.label_val.configure(text="Status: Erro de Entrada")
                    return
                
                contador_barra += 1
                progresso = contador_barra / len(blocos)

                taxa_acerto = simulacao_monte_carlo(
                    n_simulacoes, acessos, memory_size, tamanho_cache_bytes,
                    associatividade, regioes_quentes, (prob_temporal, prob_espacial, prob_quente),
                    bt, self.algoritmo_escolhido
                )

                if not self.is_running:
                    return

                self.progressbar.set(progresso)
                self.resultados.append((bt, taxa_acerto))
                self.update_idletasks()

            self.atualizar_plot()
            self.desenhar_diagrama_blocos()

            if self.resultados and self.is_running:
                tamanhos, taxas = zip(*self.resultados)
                max_hit = max(taxas)

                self.card_hit.label_val.configure(text=f"Hit Rate Máx: {max_hit*100:.2f}%")
                self.card_status.label_val.configure(text=f"Status: Concluído ({time.time() - start_time:.2f}s)")

                texto = f"// RESULTADOS SIMULAÇÃO ({self.algoritmo_escolhido})\n"
                texto += f"Tamanhos_de_bloco = [{', '.join(str(int(t)) for t in tamanhos)}];\n"
                texto += f"Taxa_media_de_acerto = [{', '.join(f'{float(t):.6f}' for t in taxas)}];"
                
                self.textbox_resultados.configure(state="normal")
                self.textbox_resultados.delete("1.0", "end")
                self.textbox_resultados.insert("1.0", texto)
                self.textbox_resultados.configure(state="disabled")

                os.makedirs("Resultados_Simulacao", exist_ok=True)
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                caminho_arquivo = os.path.join("Resultados_Simulacao", f"Simulacao_{timestamp}.csv")
                with open(caminho_arquivo, "w") as f:
                    f.write("Tamanho_Bloco,Taxa_Acerto\n")
                    for bloco, taxa in self.resultados:
                        f.write(f"{bloco},{taxa:.6f}\n")

        except Exception as e:
            if self.is_running:
                self.lbl_msg_erro.configure(text=f"[ERRO INESPERADO] {str(e)}")
                self.card_status.label_val.configure(text="Status: Falha na Execução")

    def atualizar_plot(self):
        if not self.resultados or not self.is_running:
            return
        tamanhos, taxas = zip(*self.resultados)
        tamanhos_log2 = [math.log2(tam) for tam in tamanhos]

        line, = self.ax_plot.plot(tamanhos_log2, taxas, marker='o', linewidth=2, label=self.algoritmo_escolhido)
        self.plot_lines.append(line)

        self.ax_plot.legend(facecolor='#2b2b36', edgecolor='white', labelcolor='white')
        self.canvas_plot.draw()

    def limpar_ultimo_plot(self):
        self.lbl_msg_erro.configure(text="")
        self.progressbar.set(0.0)

        self.textbox_resultados.configure(state="normal")
        self.textbox_resultados.delete("1.0", "end")
        self.textbox_resultados.configure(state="disabled")

        if self.plot_lines:
            line = self.plot_lines.pop()
            line.remove()
            if self.plot_lines:
                self.ax_plot.legend(facecolor='#2b2b36', edgecolor='white', labelcolor='white')
            else:
                legend = self.ax_plot.get_legend()
                if legend:
                    legend.remove()
            self.canvas_plot.draw()

    def limpar_plots(self):
        self.plot_lines.clear()
        self.ax_plot.clear()
        self._setup_ax_plot_style()
        self.canvas_plot.draw()

        self.progressbar.set(0.0)
        self.textbox_console.configure(state="normal")
        self.textbox_console.delete("1.0", "end")
        self.textbox_console.configure(state="disabled")

        self.textbox_resultados.configure(state="normal")
        self.textbox_resultados.delete("1.0", "end")
        self.textbox_resultados.configure(state="disabled")

        self.lbl_msg_erro.configure(text="")
        self.card_hit.label_val.configure(text="Hit Rate Máx: --%")
        self.card_status.label_val.configure(text="Status: Aguardando")
        self.limpar_mapa_calor()

    def exibir_mapa_temporal_blocos(self):
        try:
            memory_size = int(self.entry_ram.get())
            acessos = int(self.entry_acessos.get())
            prob_t = float(self.entry_prob_temp.get())
            prob_e = float(self.entry_prob_esp.get())
            prob_q = float(self.entry_prob_hot.get())
        except ValueError:
            memory_size = 1048576
            acessos = 10000
            prob_t, prob_e, prob_q = 0.2, 0.2, 0.4

        bloco_tamanho = 16
        resolucao_temporal = 50
        regioes_quentes = [64, 1024, 8192, 32768, 131072, 262144, 524288, 786432, 983040]
        acessos_mock = gerar_padrao_realista(min(acessos, 2000), memory_size, regioes_quentes, (prob_t, prob_e, prob_q))

        num_janelas = len(acessos_mock) // resolucao_temporal
        num_blocos = min(memory_size // bloco_tamanho, 64)
        heatmap = np.zeros((num_blocos, num_janelas), dtype=int)

        for i, endereco in enumerate(acessos_mock):
            tempo = i // resolucao_temporal
            bloco = (endereco // bloco_tamanho) % num_blocos
            if tempo < num_janelas:
                heatmap[bloco][tempo] += 1

        self.fig_heatmap.clear()
        ax = self.fig_heatmap.add_subplot(111)
        ax.set_facecolor('#1e1e2e')

        cax = ax.imshow(heatmap, cmap='magma', aspect='auto', origin='lower')
        cbar = self.fig_heatmap.colorbar(cax, ax=ax)
        cbar.ax.yaxis.set_tick_params(color='white')
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')
        cbar.set_label("Acessos por Bloco", color='white')

        ax.set_title("Mapa de Calor de Acessos à Memória (Espacial x Temporal)", color='#00c8ff', pad=10)
        ax.set_xlabel(f"Janelas Temporais ({resolucao_temporal} acessos/janela)", color='white')
        ax.set_ylabel("Índice do Bloco da Memória", color='white')
        ax.tick_params(colors='white')
        for spine in ax.spines.values():
            spine.set_color('#333d52')

        self.fig_heatmap.tight_layout()
        self.canvas_heatmap.draw()

    def limpar_mapa_calor(self):
        self.fig_heatmap.clear()
        ax = self.fig_heatmap.add_subplot(111)
        ax.set_facecolor('#1e1e2e')
        ax.axis('off')
        self.fig_heatmap.tight_layout()
        self.canvas_heatmap.draw()

# ==============================================================================
# 4. EXECUÇÃO DA APLICAÇÃO
# ==============================================================================

if __name__ == "__main__":
    app = CacheSimulatorApp()
    app.mainloop()
