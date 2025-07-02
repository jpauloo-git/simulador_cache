# Importações necessárias para funcionalidades diversas
import numpy as np                      # Biblioteca para computação numérica
import matplotlib.pyplot as plt        # Biblioteca para visualização gráfica
import random                          # Biblioteca padrão para geração de números aleatórios
from collections import deque          # Deque (fila dupla) para simulações de políticas de cache
import io, base64                      # Para manipulação de fluxos de bytes e codificação
from PIL import Image                  # Para manipulação de imagens
from io import BytesIO                 # Para fluxo de bytes em memória
import csv                             # Para leitura/escrita de arquivos CSV
import dearpygui.dearpygui as dpg     # Biblioteca GUI para interface gráfica
import time, sys, os                   # Utilitários do sistema e tempo
from datetime import datetime          # Para manipulação de datas e horários
import math                            # Biblioteca matemática para funções diversas

# ------------------------------------------------------------------------------
# Redirecionador de saída padrão (print) para uma tag do DearPyGUI
class DPGRedirector:
    def __init__(self, tag):
        self.tag = tag
        self.buffer = ""

    def write(self, text):
        try:
            self.buffer += text
            current_text = dpg.get_value(self.tag)
            if current_text is None:
                current_text = ""
            dpg.set_value(self.tag, current_text + text)
        except Exception as e:
            # Fallback para stdout padrão se houver erro
            print(text, end='')

    def flush(self):
        pass  # Método necessário para compatibilidade com sys.stdout

# Lista global para armazenar tags de séries de plotagem (caso visualizações sejam usadas)
plot_series_tags = []

# ------------------------------------------------------------------------------
# Verifica se um número é potência de 2 (útil para parâmetros de cache válidos)
def is_power_of_two(x):
    return (x != 0) and ((x & (x - 1)) == 0)

# ------------------------------------------------------------------------------
# Gera um padrão de acessos à memória simulando comportamentos realistas
def gerar_padrao_realista(acessos, memory_size, regioes_quentes, prob_temporal, prob_espacial, prob_quente, bloco_tamanho):
    padrao = []
    endereco_anterior = random.randint(0, memory_size - 1)
    for _ in range(acessos):
        r = random.random()
        if r < prob_temporal:
            # Repetição do endereço anterior (localidade temporal)
            endereco = endereco_anterior
        elif r < prob_temporal + prob_espacial:
            # Acesso a um endereço próximo ao anterior (localidade espacial)
            deslocamento = random.randint(-16, 16)
            endereco = max(0, min(memory_size - 1, endereco_anterior + deslocamento))
        elif r < prob_temporal + prob_espacial + prob_quente:
            # Acesso a uma região quente
            base = random.choice(regioes_quentes)
            deslocamento = random.randint(0, 3)
            endereco = min(memory_size - 1, base + deslocamento)
        else:
            # Acesso completamente aleatório
            endereco = random.randint(0, memory_size - 1)

        padrao.append(endereco)
        endereco_anterior = endereco

    return padrao

# ------------------------------------------------------------------------------
# Simulação de cache com política de substituição FIFO
def simular_cache_FIFO(padrao_acesso, cache_lines, associatividade, bloco_tamanho):
    num_conjuntos = cache_lines // associatividade
    cache = [[] for _ in range(num_conjuntos)]  # Lista de conjuntos de cache
    hits, misses = 0, 0
    conjunto_log, hit_log = [], []

    for endereco in padrao_acesso:
        bloco = endereco // bloco_tamanho
        conjunto = bloco % num_conjuntos
        conjunto_atual = cache[conjunto]

        if bloco in conjunto_atual:
            hits += 1
            hit_log.append(1)
        else:
            misses += 1
            hit_log.append(0)
            if len(conjunto_atual) < associatividade:
                conjunto_atual.append(bloco)
            else:
                conjunto_atual.pop(0)  # Removes o mais antigo
                conjunto_atual.append(bloco)

        conjunto_log.append(conjunto)

    return conjunto_log, hit_log

# ------------------------------------------------------------------------------
# Simulação de cache com política de substituição LRU (Least Recently Used)
def simular_cache_LRU(padrao_acesso, cache_lines, associatividade, bloco_tamanho):
    num_conjuntos = cache_lines // associatividade
    cache = [deque() for _ in range(num_conjuntos)]
    hits, misses = 0, 0
    conjunto_log, hit_log = [], []

    for endereco in padrao_acesso:
        bloco = endereco // bloco_tamanho
        conjunto = bloco % num_conjuntos
        conjunto_atual = cache[conjunto]

        if bloco in conjunto_atual:
            hits += 1
            hit_log.append(1)
            conjunto_atual.remove(bloco)      # Remove e reinsere no fim (mais recente)
            conjunto_atual.append(bloco)
        else:
            misses += 1
            hit_log.append(0)
            if len(conjunto_atual) >= associatividade:
                conjunto_atual.popleft()      # Remove o menos recentemente usado
            conjunto_atual.append(bloco)

        conjunto_log.append(conjunto)

    return conjunto_log, hit_log

# ------------------------------------------------------------------------------
# Simulação de cache com política de substituição LFU (Least Frequently Used)
def simular_cache_LFU(padrao_acesso, cache_lines, associatividade, bloco_tamanho):
    num_conjuntos = cache_lines // associatividade
    cache = [{} for _ in range(num_conjuntos)]  # Dict: bloco -> frequência
    hits, misses = 0, 0
    conjunto_log, hit_log = [], []

    for endereco in padrao_acesso:
        bloco = endereco // bloco_tamanho
        conjunto = bloco % num_conjuntos
        conjunto_atual = cache[conjunto]

        if bloco in conjunto_atual:
            hits += 1
            hit_log.append(1)
            conjunto_atual[bloco] += 1
        else:
            misses += 1
            hit_log.append(0)
            if len(conjunto_atual) < associatividade:
                conjunto_atual[bloco] = 1
            else:
                bloco_remover = min(conjunto_atual, key=conjunto_atual.get)
                del conjunto_atual[bloco_remover]
                conjunto_atual[bloco] = 1

        conjunto_log.append(conjunto)

    return conjunto_log, hit_log

# ------------------------------------------------------------------------------
# Simulação de cache com política de substituição aleatória (RANDOM)
def simular_cache_RANDOM(padrao_acesso, cache_lines, associatividade, bloco_tamanho):
    num_conjuntos = cache_lines // associatividade
    cache = [[] for _ in range(num_conjuntos)]
    hits, misses = 0, 0
    conjunto_log, hit_log = [], []

    for endereco in padrao_acesso:
        bloco = endereco // bloco_tamanho
        conjunto = bloco % num_conjuntos
        conjunto_atual = cache[conjunto]

        if bloco in conjunto_atual:
            hits += 1
            hit_log.append(1)
        else:
            misses += 1
            hit_log.append(0)
            if len(conjunto_atual) < associatividade:
                conjunto_atual.append(bloco)
            else:
                idx_remover = random.randint(0, associatividade - 1)
                conjunto_atual[idx_remover] = bloco

        conjunto_log.append(conjunto)

    return conjunto_log, hit_log

# ------------------------------------------------------------------------------
# Simulação de cache multinível com diversas políticas de substituição
def simular_cache_multinivel(padrao_acesso, niveis_config, algoritmos):
    """
    Simula um sistema de cache multinível corrigido para evitar Segmentation Fault
    
    Parâmetros:
    - padrao_acesso: Lista de endereços de memória acessados
    - niveis_config: Lista de tuplas (cache_lines, associatividade, bloco_tamanho) para cada nível
    - algoritmos: Lista de strings com o algoritmo de substituição para cada nível ('FIFO', 'LRU', 'LFU', 'Random')
    
    Retorna:
    - hit_rates: Lista de taxas de acerto para cada nível
    - tempo_medio: Tempo médio de acesso calculado conforme fórmula Tmed
    - total_acessos: Total de acessos à memória principal
    """
    n_niveis = len(niveis_config)
    
    if len(algoritmos) != n_niveis:
        raise ValueError("O número de algoritmos deve ser igual ao número de níveis de cache")
    
    # Inicializa contadores
    hits_por_nivel = [0] * n_niveis
    misses_por_nivel = [0] * n_niveis
    
    # Inicializa estruturas de cache adequadas para cada algoritmo
    caches = []
    for i in range(n_niveis):
        cache_lines, associatividade, bloco_tamanho = niveis_config[i]
        num_conjuntos = cache_lines // associatividade
        
        if algoritmos[i] == 'LFU':
            cache = [{} for _ in range(num_conjuntos)]
        elif algoritmos[i] == 'LRU':
            cache = [deque() for _ in range(num_conjuntos)]
        else:  # FIFO ou Random
            cache = [[] for _ in range(num_conjuntos)]
        
        caches.append((cache, num_conjuntos, associatividade, bloco_tamanho, algoritmos[i]))
    total_acessos_ram = 0
    for endereco in padrao_acesso:
        dados_encontrados = False
        
        # Processa cada nível sequencialmente
        for nivel in range(n_niveis):
            cache, num_conjuntos, associatividade, bloco_tamanho, algoritmo = caches[nivel]
            
            bloco = endereco // bloco_tamanho
            conjunto = bloco % num_conjuntos
            conjunto_atual = cache[conjunto]
            
            # Verifica se o bloco está no cache atual
            if algoritmo == 'LFU':
                if bloco in conjunto_atual:
                    # HIT
                    conjunto_atual[bloco] += 1
                    hits_por_nivel[nivel] += 1
                    dados_encontrados = True
                    break
                else:
                    # MISS
                    misses_por_nivel[nivel] += 1
            
            elif algoritmo == 'LRU':
                if bloco in conjunto_atual:
                    # HIT
                    conjunto_atual.remove(bloco)
                    conjunto_atual.append(bloco)
                    hits_por_nivel[nivel] += 1
                    dados_encontrados = True
                    break
                else:
                    # MISS
                    misses_por_nivel[nivel] += 1
            
            else:  # FIFO ou Random
                if bloco in conjunto_atual:
                    # HIT
                    hits_por_nivel[nivel] += 1
                    dados_encontrados = True
                    break
                else:
                    # MISS
                    misses_por_nivel[nivel] += 1
        
        # Se não encontrou em nenhum nível, acessa a RAM
        if not dados_encontrados:
            total_acessos_ram += 1
        
        # Carrega o bloco em todos os níveis (do RAM para cima)
        if not dados_encontrados:
            for nivel in range(n_niveis):
                cache, num_conjuntos, associatividade, bloco_tamanho, algoritmo = caches[nivel]
                bloco = endereco // bloco_tamanho
                conjunto = bloco % num_conjuntos
                conjunto_atual = cache[conjunto]
                
                # Insere o bloco no cache usando a política apropriada
                if algoritmo == 'LFU':
                    if len(conjunto_atual) < associatividade:
                        conjunto_atual[bloco] = 1
                    else:
                        # Remove o menos frequente
                        bloco_remover = min(conjunto_atual, key=conjunto_atual.get)
                        del conjunto_atual[bloco_remover]
                        conjunto_atual[bloco] = 1
                
                elif algoritmo == 'LRU':
                    if len(conjunto_atual) < associatividade:
                        conjunto_atual.append(bloco)
                    else:
                        # Remove o menos recente
                        conjunto_atual.popleft()
                        conjunto_atual.append(bloco)
                
                elif algoritmo == 'FIFO':
                    if len(conjunto_atual) < associatividade:
                        conjunto_atual.append(bloco)
                    else:
                        # Remove o primeiro (mais antigo)
                        conjunto_atual.pop(0)
                        conjunto_atual.append(bloco)
                
                else:  # Random
                    if len(conjunto_atual) < associatividade:
                        conjunto_atual.append(bloco)
                    else:
                        # Remove aleatório
                        idx_remover = random.randint(0, associatividade - 1)
                        conjunto_atual[idx_remover] = bloco
    
    # Calcula taxas de acerto
    total_acessos = len(padrao_acesso)
    hit_rates = []
    
    if total_acessos > 0:
        # L1: todos os acessos passam por ele
        hit_rates.append(hits_por_nivel[0] / total_acessos)
        
        # L2, L3: apenas os misses do nível anterior
        for i in range(1, n_niveis):
            acessos_nivel = misses_por_nivel[i-1]
            if acessos_nivel > 0:
                hit_rates.append(hits_por_nivel[i] / acessos_nivel)
            else:
                hit_rates.append(0.0)
    else:
        hit_rates = [0.0] * n_niveis
    
    return hit_rates, [], total_acessos_ram

# ------------------------------------------------------------------------------
# Calcula o tempo médio de acesso para um sistema de cache multinível
def calcular_tempo_medio_acesso(hit_rates, tempos_acesso):
    """
    Calcula o tempo médio de acesso para um sistema de cache multinível
    
    Parâmetros:
    - hit_rates: Lista de taxas de acerto para cada nível
    - tempos_acesso: Lista de tempos de acesso para cada nível, incluindo memória principal
    
    Retorna:
    - Tempo médio de acesso segundo a equação Tmed
    """
    if len(hit_rates) + 1 != len(tempos_acesso):
        raise ValueError("O número de tempos de acesso deve ser igual ao número de níveis de cache + 1 (RAM)")
    
    n_niveis = len(hit_rates)
    tempo_medio = 0
    
    # Calcula o tempo médio de acesso para cada nível, começando pelo último
    # Utiliza a fórmula recursiva Tmed conforme equação 4.8 do material
    t_memoria = tempos_acesso[-1]  # Tempo da memória principal (RAM)
    
    # Inicializa com tempo da RAM
    t_nivel_seguinte = t_memoria
    
    # Calcula do último nível de cache para o primeiro
    for i in range(n_niveis - 1, -1, -1):
        hit_rate = hit_rates[i]
        t_nivel_atual = tempos_acesso[i]
        
        # Fórmula: T_i_acesso = p_i * T_i + (1 - p_i) * T_i+1_acesso
        t_nivel_acesso = hit_rate * t_nivel_atual + (1 - hit_rate) * t_nivel_seguinte
        
        # Este nível se torna o próximo para o nível anterior
        t_nivel_seguinte = t_nivel_acesso
    
    # O tempo médio final é o tempo de acesso calculado para o L1
    tempo_medio = t_nivel_seguinte
    
    return tempo_medio

# ------------------------------------------------------------------------------
# Execução de simulações Monte Carlo para cache multinível
def simulacao_monte_carlo_multinivel(n_simulacoes, acessos, memory_size, niveis_config, algoritmos, 
                                     tempos_acesso, regioes_quentes, probs, bloco_tamanho):
    """
    Executa múltiplas simulações de cache multinível e retorna estatísticas
    
    Parâmetros:
    - n_simulacoes: Número de simulações a executar
    - acessos: Número de acessos à memória em cada simulação
    - memory_size: Tamanho total da memória principal
    - niveis_config: Lista de tuplas (cache_lines, associatividade, bloco_tamanho) para cada nível
    - algoritmos: Lista de algoritmos para cada nível ('FIFO', 'LRU', 'LFU', 'Random')
    - tempos_acesso: Lista de tempos de acesso para cada nível + RAM
    - regioes_quentes: Lista de endereços de regiões de acesso frequente
    - probs: Tupla (prob_temporal, prob_espacial, prob_quente)
    - bloco_tamanho: Tamanho do bloco em bytes
    
    Retorna:
    - média das taxas de acerto por nível
    - tempo médio de acesso
    """
    hit_rates_total = [[] for _ in range(len(niveis_config))]
    tempos_medios = []
    
    for i in range(n_simulacoes):
        padrao = gerar_padrao_realista(acessos, memory_size, regioes_quentes, *probs, bloco_tamanho)
        hit_rates, hit_logs, total_ram = simular_cache_multinivel(padrao, niveis_config, algoritmos)
        
        for nivel, taxa in enumerate(hit_rates):
            hit_rates_total[nivel].append(taxa)
        
        tempo_medio = calcular_tempo_medio_acesso(hit_rates, tempos_acesso)
        tempos_medios.append(tempo_medio)
    
    # Calcula médias das taxas de acerto por nível
    hit_rates_media = [np.mean(taxas) for taxas in hit_rates_total]
    hit_rates_std = [np.std(taxas) for taxas in hit_rates_total]
    tempo_medio_media = np.mean(tempos_medios)
    tempo_medio_std = np.std(tempos_medios)
    
    # Imprime estatísticas
    print(f"--- Resultados: {acessos} Acessos - Cache Multinível - Bloco de {bloco_tamanho} ---\n")
    for i, (media, std) in enumerate(zip(hit_rates_media, hit_rates_std)):
        print(f"Taxa de Acerto L{i+1}: {media:.4f} (±{std:.4f})")
    
    print(f"\nTempo Médio de Acesso: {tempo_medio_media:.2f} ns (±{tempo_medio_std:.2f})")
    
    return hit_rates_media, tempo_medio_media

# ------------------------------------------------------------------------------
# Variável global que armazena o algoritmo de substituição selecionado
algoritmo_escolhido = "FIFO"

# Callback para seleção do algoritmo via GUI
def selecionar_algoritmo(sender, app_data):
    global algoritmo_escolhido
    algoritmo_escolhido = app_data

# ------------------------------------------------------------------------------
# Geração de mapa de calor (heatmap) dos acessos por bloco ao longo do tempo
def mapa_temporal_blocos():
    try:
        # Obter parâmetros da interface
        memory_size = int(dpg.get_value("memory_size"))
        blocos = dpg.get_value("blocos")  # String com os tamanhos dos blocos
        bloco_tamanho = int(blocos.split(",")[0])  # Usar o primeiro tamanho de bloco
        acessos = int(dpg.get_value("acessos"))
        prob_temporal = float(dpg.get_value("prob_temporal"))
        prob_espacial = float(dpg.get_value("prob_espacial"))
        prob_quente = float(dpg.get_value("prob_quente"))
        
        # Lista predefinida de regiões quentes
        regioes_quentes = [64, 1024, 8192, 32768, 131072, 262144, 524288, 786432, 983040]
        
        # Gerar padrão de acesso
        padrao_acesso = gerar_padrao_realista(acessos, memory_size, regioes_quentes, 
                                            prob_temporal, prob_espacial, prob_quente, 
                                            bloco_tamanho)
        
        # Criar matriz do heatmap
        resolucao_temporal = 100
        num_janelas = max(1, len(padrao_acesso) // resolucao_temporal)
        resolucao_blocos = 256
        num_blocos = max(1, memory_size // bloco_tamanho)
        num_blocos_agrupados = max(1, num_blocos // resolucao_blocos)
        heatmap = np.zeros((num_blocos_agrupados, num_janelas), dtype=int)

        for i, endereco in enumerate(padrao_acesso):
            tempo = i // resolucao_temporal
            bloco = endereco // bloco_tamanho
            bloco_agrupado = min(bloco // resolucao_blocos, num_blocos_agrupados - 1)
            tempo = min(tempo, num_janelas - 1)
            heatmap[bloco_agrupado][tempo] += 1

        # Criar e salvar o heatmap
        plt.figure(figsize=(6, 4))
        plt.imshow(heatmap, cmap='hot', aspect='auto', origin='lower', interpolation='nearest', vmin=0, vmax=np.max(heatmap) // 5 + 1)
        plt.colorbar(label="Número de acessos por bloco")
        plt.title(f"Evolução dos Acessos à Memória por Bloco (Tamanho: {bloco_tamanho} bytes)")
        plt.xlabel(f"Grupos de {resolucao_temporal} Acessos")
        plt.ylabel("Bloco de Memória")
        plt.tight_layout()  # Ajusta automaticamente o layout
        
        # Salvar em um arquivo temporário
        if not os.path.exists('Heatmaps'):
            os.makedirs('Heatmaps')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'Heatmaps/heatmap_{timestamp}.png'
        plt.savefig(filename, dpi=100, bbox_inches='tight')
        plt.close()

        # Atualizar o heatmap na interface
        if dpg.does_item_exist("heatmap_texture"):
            dpg.delete_item("heatmap_texture")
        
        width, height, channels, data = dpg.load_image(filename)
        with dpg.texture_registry():
            texture_id = dpg.add_static_texture(width, height, data, tag="heatmap_texture")
        
        if dpg.does_item_exist("heatmap_image"):
            dpg.delete_item("heatmap_image")
            dpg.delete_item("heatmap_text")
        
        dpg.add_image(texture_id, parent="heatmap_group", tag="heatmap_image", width=540, height=450)
        dpg.add_text(f"Tamanho do Bloco: {bloco_tamanho} bytes", parent="heatmap_group", tag="heatmap_text")
        
    except Exception as e:
        dpg.set_value("mensagem_erro", f"Erro ao gerar heatmap: {str(e)}")

# ------------------------------------------------------------------------------
# Execução de várias simulações (Monte Carlo) para avaliar desempenho do algoritmo escolhido
def simulacao_monte_carlo(n_simulacoes, acessos, memory_size, cache_lines, associatividade, regioes_quentes, probs, bloco_tamanho):
    taxas_acerto = []
    hits_totais = []
    misses_totais = []

    for i in range(n_simulacoes):
        padrao = gerar_padrao_realista(acessos, memory_size, regioes_quentes, *probs, bloco_tamanho)
        
        # Seleciona e executa o algoritmo de substituição
        if algoritmo_escolhido == 'FIFO':
            conjunto_log, hit_log = simular_cache_FIFO(padrao, cache_lines, associatividade, bloco_tamanho)
        elif algoritmo_escolhido == 'LRU':
            conjunto_log, hit_log = simular_cache_LRU(padrao, cache_lines, associatividade, bloco_tamanho)
        elif algoritmo_escolhido == 'LFU':
            conjunto_log, hit_log = simular_cache_LFU(padrao, cache_lines, associatividade, bloco_tamanho)
        elif algoritmo_escolhido == 'Random':
            conjunto_log, hit_log = simular_cache_RANDOM(padrao, cache_lines, associatividade, bloco_tamanho)
        else:
            raise ValueError(f"Algoritmo de substituição desconhecido: {algoritmo_escolhido}")

        hits = sum(hit_log)
        misses = len(hit_log) - hits
        taxa_acerto = hits / len(hit_log)
        
        # Armazena resultados desta simulação
        taxas_acerto.append(taxa_acerto)
        hits_totais.append(hits)
        misses_totais.append(misses)

    # Exibe estatísticas gerais
    print(f"--- Resultados: {acessos} Acessos - Bloco de {bloco_tamanho} ---\n")
    print(f"Média da Taxa de Acerto: {np.mean(taxas_acerto):.2f}")
    print(f"Desvio Padrão da Taxa de Acerto: {np.std(taxas_acerto):.2f}")
    print(f"Máximo: {max(taxas_acerto):.2f}, Mínimo: {min(taxas_acerto):.2f}")

    # Parte do plot do mapa de acessos. COmentada porque NÃO FUNCIONA!!!!!
        # if i == 0:
            # mapa_temporal_blocos(padrao, memory_size, bloco_tamanho, resolucao_temporal=100)

    print(f"--- Resultados: {acessos} Acessos - Bloco de {bloco_tamanho} ---\n")
    print(f"Média da Taxa de Acerto: {np.mean(taxas_acerto):.4f}")
    print(f"Desvio padrão da Taxa de Acerto: {np.std(taxas_acerto):.4f}\n")   # print(f"Total médio de acessos: {acessos}")
    
    # Parte comentada ANTIGA para debug!!!!!
# --------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
    # print(f"Média de Cache Hits: {np.mean(hits_totais):.2f}")
    # print(f"Variância Taxa de Acerto: {np.var(hits_totais):.2f}")
    # print(f"Média Taxa de Erro: {np.mean(misses_totais):.2f}")
    # print(f"Variância Taxa de Erro: {np.var(misses_totais):.2f}")
    # print(f"Média da Taxa de Acerto: {np.mean(taxas_acerto):.4f}")
    # print(f"Desvio padrão da Taxa de Acerto: {np.std(taxas_acerto):.4f}\n")
	
	# Atualiza o conteúdo da caixa de texto 'Resumo' na interface
	# ATENÇÃO: Após a alteração de desvio da saída padrão (DPGRedirector), tanto faz usar a 
	# caixa de texto 'Resumo' ou a função 'print'
	
    # Texto = f"Total de acessos: {acessos}\n"
    # Texto += f"Média de Cache Hits: {np.mean(hits_totais):.2f}\n"
    # Texto += f"Variância de Cache Hits: {np.var(hits_totais):.2f}\n"
    # Texto += f"Média de Cache Misses: {np.mean(misses_totais):.2f}\n"
    # Texto += f"Variância de Cache Misses: {np.var(misses_totais):.2f}\n"
    # Texto += f"Média da Taxa de Acerto: {np.mean(taxas_acerto):.4f}\n"
    # Texto += f"Desvio padrão da Taxa de Acerto: {np.std(taxas_acerto):.4f}\n"
	
    # Atualiza dados da simulação na Caixa de tetxto Resumo
    # dpg.set_value("Resumo", Texto)
    return np.mean(taxas_acerto)
# --------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------

import dearpygui.dearpygui as dpg

from collections import deque

resultados = []


def rodar_simulacao_callback():
    start_time = time.time()
    print(f"            ---   Algoritmo: {algoritmo_escolhido} ---\n")
    global resultados
    dpg.set_value("mensagem_erro", "")  # Limpa mensagem antiga

    try:
        # Leitura dos valores
        memory_size = dpg.get_value("memory_size")
        acessos = dpg.get_value("acessos")
        tamanho_cache_bytes = dpg.get_value("tamanho_cache")
        associatividade = dpg.get_value("associatividade")
        n_simulacoes = dpg.get_value("n_simulacoes")
        prob_temporal = dpg.get_value("prob_temporal")
        prob_espacial = dpg.get_value("prob_espacial")
        prob_quente = dpg.get_value("prob_quente")
        blocos = dpg.get_value("blocos")
        blocos = [int(b.strip()) for b in blocos.split(",")]

        regioes_quentes = [
            64, 1024, 8192, 32768, 131072, 262144, 524288, 786432, 983040
        ]

        # --- VERIFICAÇÕES ---

        if not (2**20 <= memory_size <= 2**30) or (memory_size & (memory_size-1)) != 0:
            dpg.set_value("mensagem_erro", "Erro: Memory Size deve ser potência de 2 entre 2^20 e 2^30.")
            return

        if not is_power_of_two(associatividade):
            dpg.set_value("mensagem_erro", "Erro: Associatividade deve ser potência de 2 maior que zero.")
            return

        if (tamanho_cache_bytes & (tamanho_cache_bytes-1)) != 0 or tamanho_cache_bytes >= memory_size:
            dpg.set_value("mensagem_erro", "Erro: Tamanho da Cache deve ser potência de 2 e menor que Memory Size.")
            return

        for bloco in blocos:
            if bloco <= 0 or bloco >= memory_size or not is_power_of_two(bloco):
                dpg.set_value("mensagem_erro", f"Tamanho do Bloco deve ser potência de 2 e menor que Memory Size. Valor fornecido: {bloco}")
                return
            cache_lines = tamanho_cache_bytes // bloco
            num_conjuntos = cache_lines // associatividade
            if num_conjuntos < 1:
                dpg.set_value("mensagem_erro", f"Erro: Associatividade {associatividade} inválida para bloco {bloco}.")
                return

        if not (0 <= prob_temporal <= 1) or not (0 <= prob_espacial <= 1) or not (0 <= prob_quente <= 1):
            dpg.set_value("mensagem_erro", "Erro: Probabilidades devem ser entre 0 e 1.")
            return

        # --- FIM VERIFICAÇÕES ---

        resultados.clear()
        contador_barra = 0
        progresso = 0.01		# Mostra um andamento mínimo na barra de progresso para indicar que a nova simulação iniciou
        dpg.set_value("barra", progresso)
        dpg.set_value("texto", "Simulação Iniciada")
        for bt in blocos:
            contador_barra += 1		
            progresso = contador_barra / len(blocos)            
            cache_lines = tamanho_cache_bytes // bt
            taxas_acerto = simulacao_monte_carlo(
                n_simulacoes,
                acessos,
                memory_size,
                cache_lines,
                associatividade,
                regioes_quentes,
                (prob_temporal, prob_espacial, prob_quente),
                bt
            )
            dpg.set_value("barra", progresso)
            dpg.set_value("texto", f"{int(progresso*100)}% concluído")
            resultados.append((bt, taxas_acerto))
            dpg.split_frame()  # Permite que a interface atualize
		# ao final, exibir resultados
        atualizar_plot()

        if resultados:
            tamanhos, taxas = zip(*resultados)
            texto = f"Tamanhos_de_bloco = [{', '.join(str(int(t)) for t in tamanhos)}];\n"
            texto += f"Taxa_media_de_acerto = [{', '.join(f'{float(t):.6f}' for t in taxas)}];"
        
            # Atualiza o conteúdo da caixa de texto na interface
            dpg.set_value("resultados_box", texto)
        
            # Opcional: também salva os resultados em um arquivo CSV
            
			# Define o nome da subpasta
            subpasta = "Resultados da Simulacao"
			# Cria a subpasta se não existir
            os.makedirs(subpasta, exist_ok=True)
            # Captura data e hora atual
            agora = datetime.now()
            # Formata para uma string segura para nome de arquivo
            timestamp = agora.strftime("%Y-%m-%d_%H-%M-%S")
			# Caminho completo do arquivo
            nome_arquivo = f"Resultados da Simulacao - {timestamp}.csv"
            caminho_arquivo = os.path.join(subpasta, nome_arquivo)
            with open(caminho_arquivo, "w") as f:
                f.write(f"- Algoritmo = {algoritmo_escolhido}\n- Associatividade = {associatividade}\n- Acessos = {acessos}\n- Cache = {tamanho_cache_bytes}\n- P_tem = {prob_temporal}\n- P_espa = {prob_espacial}\n- P_reg_quente = {prob_quente}\n")
                f.write("\nTamanho_Bloco,Taxa_Acerto\n")
                for bloco, taxa in resultados:
                    f.write(f"{bloco},{taxa:.6f}\n")
    
    except Exception as e:
        dpg.set_value("mensagem_erro", f"Erro inesperado: {str(e)}")
    # Mede tempo de simulação:
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Tempo de execução: {elapsed_time:.2f} segundos\n")
    print("          ------------++-------------     \n")


# Função para executar simulação de cache multinível
def rodar_simulacao_multinivel_callback():
    start_time = time.time()
    global resultados
    
    dpg.set_value("mensagem_erro", "")
    
    try:
        # Verificações de segurança antes de começar
        if not dpg.does_item_exist("y_axis"):
            dpg.set_value("mensagem_erro", "Erro: Interface não está pronta.")
            return
        
        # Verifica se todos os valores são válidos
        valores_obrigatorios = [
            ("memory_size_multi", "Memory Size"),
            ("acessos_multi", "Acessos"),
            ("n_simulacoes_multi", "N Simulações"),
            ("bloco_multi", "Tamanho do Bloco")
        ]
        
        for tag, nome in valores_obrigatorios:
            valor = dpg.get_value(tag)
            if valor is None or valor <= 0:
                dpg.set_value("mensagem_erro", f"Erro: {nome} deve ser um valor positivo.")
                return
        
        # Leitura dos valores da interface
        memory_size = dpg.get_value("memory_size_multi")
        acessos = dpg.get_value("acessos_multi")
        n_simulacoes = dpg.get_value("n_simulacoes_multi")
        bloco_tamanho = dpg.get_value("bloco_multi")
        
        # Probabilidades
        prob_temporal = dpg.get_value("prob_temporal_multi")
        prob_espacial = dpg.get_value("prob_espacial_multi")
        prob_quente = dpg.get_value("prob_quente_multi")
        
        # Configuração dos níveis de cache
        niveis_config = []
        algoritmos = []
        tempos_acesso = []
        
        # Configuração L1 (sempre presente)
        tamanho_cache_l1 = dpg.get_value("tamanho_cache_l1")
        associatividade_l1 = dpg.get_value("associatividade_l1")
        algoritmo_l1 = dpg.get_value("algoritmo_l1")
        tempo_l1 = dpg.get_value("tempo_l1")
        
        cache_lines_l1 = tamanho_cache_l1 // bloco_tamanho
        niveis_config.append((cache_lines_l1, associatividade_l1, bloco_tamanho))
        algoritmos.append(algoritmo_l1)
        tempos_acesso.append(tempo_l1)
        
        # Configuração L2 (opcional)
        usar_l2 = dpg.get_value("usar_l2")
        if usar_l2:
            tamanho_cache_l2 = dpg.get_value("tamanho_cache_l2")
            associatividade_l2 = dpg.get_value("associatividade_l2")
            algoritmo_l2 = dpg.get_value("algoritmo_l2")
            tempo_l2 = dpg.get_value("tempo_l2")
            
            cache_lines_l2 = tamanho_cache_l2 // bloco_tamanho
            niveis_config.append((cache_lines_l2, associatividade_l2, bloco_tamanho))
            algoritmos.append(algoritmo_l2)
            tempos_acesso.append(tempo_l2)
        
        # Configuração L3 (opcional)
        usar_l3 = dpg.get_value("usar_l3")
        if usar_l3:
            tamanho_cache_l3 = dpg.get_value("tamanho_cache_l3")
            associatividade_l3 = dpg.get_value("associatividade_l3")
            algoritmo_l3 = dpg.get_value("algoritmo_l3")
            tempo_l3 = dpg.get_value("tempo_l3")
            
            cache_lines_l3 = tamanho_cache_l3 // bloco_tamanho
            niveis_config.append((cache_lines_l3, associatividade_l3, bloco_tamanho))
            algoritmos.append(algoritmo_l3)
            tempos_acesso.append(tempo_l3)
        
        # Tempo da memória principal (RAM)
        tempo_ram = dpg.get_value("tempo_ram")
        tempos_acesso.append(tempo_ram)
        
        # --- VERIFICAÇÕES ---
        if not (2**20 <= memory_size <= 2**30) or (memory_size & (memory_size-1)) != 0:
            dpg.set_value("mensagem_erro", "Erro: Memory Size deve ser potência de 2 entre 2^20 e 2^30.")
            return

        for nivel, (cache_lines, associatividade, _) in enumerate(niveis_config):
            if not is_power_of_two(associatividade):
                dpg.set_value("mensagem_erro", f"Erro: Associatividade do nível L{nivel+1} deve ser potência de 2.")
                return
                
            num_conjuntos = cache_lines // associatividade
            if num_conjuntos < 1:
                dpg.set_value("mensagem_erro", f"Erro: Associatividade {associatividade} inválida para cache L{nivel+1}.")
                return

        if not (0 <= prob_temporal <= 1) or not (0 <= prob_espacial <= 1) or not (0 <= prob_quente <= 1):
            dpg.set_value("mensagem_erro", "Erro: Probabilidades devem ser entre 0 e 1.")
            return
            
        if not is_power_of_two(bloco_tamanho) or bloco_tamanho <= 0 or bloco_tamanho >= memory_size:
            dpg.set_value("mensagem_erro", f"Erro: Tamanho do Bloco deve ser potência de 2 e menor que Memory Size. Valor: {bloco_tamanho}")
            return

        # Verificações adicionais para cache multinível
        # Verifica se os tamanhos das caches são potências de 2 e menores que a memória principal
        tamanho_cache_l1 = niveis_config[0][0] * bloco_tamanho
        if not is_power_of_two(tamanho_cache_l1) or tamanho_cache_l1 >= memory_size:
            dpg.set_value("mensagem_erro", "Erro: Tamanho da Cache L1 deve ser potência de 2 e menor que Memory Size.")
            return

        if usar_l2:
            tamanho_cache_l2 = niveis_config[1][0] * bloco_tamanho
            if not is_power_of_two(tamanho_cache_l2) or tamanho_cache_l2 >= memory_size:
                dpg.set_value("mensagem_erro", "Erro: Tamanho da Cache L2 deve ser potência de 2 e menor que Memory Size.")
                return
            if tamanho_cache_l2 <= tamanho_cache_l1:
                dpg.set_value("mensagem_erro", "Erro: Tamanho da Cache L2 deve ser maior que L1.")
                return

        if usar_l3:
            if not usar_l2:
                dpg.set_value("mensagem_erro", "Erro: Não é possível usar L3 sem L2.")
                return
            tamanho_cache_l3 = niveis_config[2][0] * bloco_tamanho
            if not is_power_of_two(tamanho_cache_l3) or tamanho_cache_l3 >= memory_size:
                dpg.set_value("mensagem_erro", "Erro: Tamanho da Cache L3 deve ser potência de 2 e menor que Memory Size.")
                return
            if tamanho_cache_l3 <= tamanho_cache_l2:
                dpg.set_value("mensagem_erro", "Erro: Tamanho da Cache L3 deve ser maior que L2.")
                return

        # Verifica se os tempos de acesso seguem a hierarquia
        if tempo_l1 <= 0:
            dpg.set_value("mensagem_erro", "Erro: Tempo de acesso L1 deve ser positivo.")
            return

        if usar_l2:
            if tempo_l2 <= tempo_l1:
                dpg.set_value("mensagem_erro", "Erro: Tempo de acesso L2 deve ser maior que L1.")
                return

        if usar_l3:
            if tempo_l3 <= tempo_l2:
                dpg.set_value("mensagem_erro", "Erro: Tempo de acesso L3 deve ser maior que L2.")
                return

        if tempo_ram <= (tempo_l3 if usar_l3 else (tempo_l2 if usar_l2 else tempo_l1)):
            dpg.set_value("mensagem_erro", "Erro: Tempo de acesso RAM deve ser maior que o último nível de cache.")
            return
        # --- FIM VERIFICAÇÕES ---

        resultados.clear()
        dpg.set_value("barra", 0.01)  # Mostra um andamento mínimo
        dpg.set_value("texto", "Simulação Iniciada")
        
        # Regiões quentes para o padrão de acesso
        regioes_quentes = [
            64, 1024, 8192, 32768, 131072, 262144, 524288, 786432, 983040
        ]
        
        # Executa simulação multinível
        hit_rates, tempo_medio = simulacao_monte_carlo_multinivel(
            n_simulacoes,
            acessos,
            memory_size,
            niveis_config,
            algoritmos,
            tempos_acesso,
            regioes_quentes,
            (prob_temporal, prob_espacial, prob_quente),
            bloco_tamanho
        )
        
        dpg.set_value("barra", 1.0)
        dpg.set_value("texto", "100% concluído")
        
        # Adiciona verificação de interrupção durante a simulação
        dpg.split_frame()  # Permite cancelamento durante execução longa
        
        # Formata e exibe os resultados
        tipos_cache = []
        for i, algoritmo in enumerate(algoritmos):
            tipos_cache.append(f"L{i+1}-{algoritmo}")
        
        # Adiciona ao gráfico
        plot_series = f"plot_multi_{len(plot_series_tags)}"
        plot_series_tags.append(plot_series)
        
        # Para o gráfico, usamos o tamanho do bloco e a taxa de acerto do L1
        tamanho_log2 = math.log2(bloco_tamanho)
        taxa_l1 = hit_rates[0]
        
        dpg.add_line_series(
            [tamanho_log2],  # X: log2 do tamanho do bloco
            [taxa_l1],      # Y: taxa de acerto do L1
            label=f"Multi: {'-'.join(algoritmos)}",
            parent="y_axis",
            tag=plot_series,
            show=True
        )
        dpg.fit_axis_data("x_axis")
        dpg.fit_axis_data("y_axis")
        
        # Formatação dos resultados para exibição
        texto = f"Cache_Multinivel = [{' -> '.join(tipos_cache)}];\n"
        texto += f"Taxa_media_de_acerto = [{', '.join(f'{float(t):.6f}' for t in hit_rates)}];\n"
        texto += f"Tempo_medio_acesso = {tempo_medio:.2f} ns;"
        
        # Atualiza a caixa de resultados
        dpg.set_value("resultados_box", texto)
        
        # Salva os resultados em um arquivo CSV
        subpasta = "Resultados da Simulacao"
        os.makedirs(subpasta, exist_ok=True)
        agora = datetime.now()
        timestamp = agora.strftime("%Y-%m-%d_%H-%M-%S")
        nome_arquivo = f"Resultados da Simulacao Multinivel - {timestamp}.csv"
        caminho_arquivo = os.path.join(subpasta, nome_arquivo)
        
        with open(caminho_arquivo, "w") as f:
            f.write(f"- Algoritmos = {', '.join(algoritmos)}\n")
            f.write(f"- Acessos = {acessos}\n")
            f.write(f"- Tamanhos_Cache = {', '.join(str(config[0]*config[2]) for config in niveis_config)}\n")
            f.write(f"- Associatividade = {', '.join(str(config[1]) for config in niveis_config)}\n")
            f.write(f"- Tempos_Acesso = {', '.join(str(t) for t in tempos_acesso)}\n")
            f.write(f"- P_tem = {prob_temporal}\n- P_espa = {prob_espacial}\n- P_reg_quente = {prob_quente}\n")
            f.write(f"- Bloco = {bloco_tamanho}\n")
            
            f.write("\nNivel,Taxa_Acerto\n")
            for i, taxa in enumerate(hit_rates):
                f.write(f"L{i+1},{taxa:.6f}\n")
            f.write(f"Tempo_Medio,{tempo_medio:.2f}\n")
        
    except Exception as e:
        dpg.set_value("mensagem_erro", f"Erro inesperado: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Mede tempo de simulação
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Tempo de execução: {elapsed_time:.2f} segundos\n")
    print("          ------------++-------------     \n")

# Função de limpeza para evitar Segmentation Fault ao fechar
def cleanup_on_exit():
    """Limpa recursos antes de fechar a aplicação"""
    global plot_series_tags
    
    try:
        # Limpa todos os plots
        for tag in plot_series_tags:
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        
        plot_series_tags.clear()
        
        # Limpa texturas se existirem
        if dpg.does_item_exist("heatmap_texture"):
            dpg.delete_item("heatmap_texture")
        
        # Força limpeza do matplotlib
        plt.close('all')
        
        print("Limpeza concluída com sucesso.")
        
    except Exception as e:
        print(f"Erro durante limpeza: {e}")

# Callback para fechar a aplicação de forma segura
def close_callback():
    """Callback para fechar a aplicação com limpeza adequada"""
    try:
        cleanup_on_exit()
    except Exception as e:
        print(f"Erro durante limpeza: {e}")
    finally:
        dpg.stop_dearpygui()

# ------------------------------------------------------------------------------
# Adicione estas funções antes da criação da interface:

def atualizar_plot():
    """Atualiza o gráfico com os resultados da simulação"""
    global plot_series_tags
    
    # Verifica se o eixo existe antes de usar
    if not dpg.does_item_exist("y_axis"):
        print("Erro: 'y_axis' não existe.")
        return

    # Verifica se há resultados
    if not resultados:
        print("Nenhum resultado para plotar.")
        return
    
    try:
        tamanhos, taxas = zip(*resultados)
        
        # Verifica se os dados são válidos
        if len(tamanhos) == 0 or len(taxas) == 0:
            print("Dados vazios para plotar.")
            return
        
        # Calcula log2 dos tamanhos com verificação
        tamanhos_log2 = []
        for tam in tamanhos:
            if tam > 0:
                tamanhos_log2.append(math.log2(tam))
            else:
                print(f"Tamanho inválido: {tam}")
                return
        
        # Verifica consistência
        if len(tamanhos_log2) != len(taxas):
            print("Erro: tamanhos_log2 e taxas têm tamanhos diferentes")
            return
        
        # Cria uma nova série para o plot
        plot_series = f"plot_{len(plot_series_tags)}"
        plot_series_tags.append(plot_series)
        
        dpg.add_line_series(
            tamanhos_log2,
            list(taxas),  # Converte para lista para garantir compatibilidade
            label=f"{algoritmo_escolhido}",
            parent="y_axis",
            tag=plot_series,
            show=True
        )
        
        # Atualiza os limites dos eixos
        dpg.fit_axis_data("x_axis")
        dpg.fit_axis_data("y_axis")
        
        print(f"Plot adicionado: {plot_series}")
        
    except Exception as e:
        print(f"Erro ao atualizar plot: {e}")
        import traceback
        traceback.print_exc()

def limpar_ultimo_plot():
    """Remove o último plot adicionado"""
    global plot_series_tags
    
    try:
        dpg.set_value("mensagem_erro", "")
        dpg.set_value("barra", 0.0)
        dpg.set_value("texto", "0% concluído")
        dpg.set_value("resultados_box", "")
        
        if plot_series_tags:
            ultimo_tag = plot_series_tags.pop()
            # Verifica se o item existe antes de deletar
            if dpg.does_item_exist(ultimo_tag):
                dpg.delete_item(ultimo_tag)
                print(f"Apagado: {ultimo_tag}")
            else:
                print(f"Item não existe: {ultimo_tag}")
        else:
            print("Nenhum plot para remover.")
            
    except Exception as e:
        print(f"Erro ao limpar último plot: {e}")

def limpar_plots():
    """Remove todos os plots"""
    global plot_series_tags
    
    try:
        # Limpa todos os plots
        for tag in plot_series_tags:
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        
        plot_series_tags.clear()
        
        # Limpa apenas os filhos do y_axis, não o próprio eixo
        if dpg.does_item_exist("y_axis"):
            dpg.delete_item("y_axis", children_only=True)
        
        # Reseta interface
        dpg.set_value("barra", 0.0)
        dpg.set_value("texto", "0% concluído")
        dpg.set_value("Resumo", "")
        dpg.set_value("resultados_box", "")
        dpg.set_value("mensagem_erro", "")
        
        print("Todos os plots foram limpos.")
        
    except Exception as e:
        print(f"Erro ao limpar plots: {e}")

def limpar_heatmap():
    """Remove o heatmap atual"""
    try:
        if dpg.does_item_exist("heatmap_image"):
            dpg.delete_item("heatmap_image")
        if dpg.does_item_exist("heatmap_text"):
            dpg.delete_item("heatmap_text")
        if dpg.does_item_exist("heatmap_texture"):
            dpg.delete_item("heatmap_texture")
        
        print("Heatmap removido.")
        
    except Exception as e:
        print(f"Erro ao limpar heatmap: {e}")

# Modifica a parte final do código onde a interface é criada:
if __name__ == "__main__":
    try:
        dpg.create_context()
        
        # Criar interface primeiro - removendo width e height fixos
        with dpg.window(label="Simulação de Cache", tag="Primary Window"):
            with dpg.tab_bar(tag="tab_bar"):
                with dpg.tab(label="Cache Única", tag="cache_unica_tab"):
                    dpg.add_input_int(label="Memory Size", default_value=1048576, tag="memory_size", width=200)
                    dpg.add_input_int(label="Acessos", default_value=10000, tag="acessos", width=200)
                    dpg.add_input_int(label="Tamanho Cache (Bytes)", default_value=8192, tag="tamanho_cache", width=200)
                    dpg.add_input_int(label="Associatividade", default_value=16, tag="associatividade", width=200)
                    dpg.add_input_int(label="N Simulações", default_value=10, tag="n_simulacoes", width=200)
                    
                    dpg.add_separator()
                    dpg.add_input_float(label="Probabilidade Temporal", default_value=0.2, tag="prob_temporal", width=200)
                    dpg.add_input_float(label="Probabilidade Espacial", default_value=0.2, tag="prob_espacial", width=200)
                    dpg.add_input_float(label="Probabilidade Região Quente", default_value=0.4, tag="prob_quente", width=200)
                    
                    dpg.add_separator()
                    dpg.add_input_text(label="Tamanhos de Bloco", default_value="2,4,8,16,32,64,128,256,512", tag="blocos", width=400)

                with dpg.tab(label="Cache Multinível", tag="cache_multinivel_tab"):
                    dpg.add_input_int(label="Memory Size", default_value=1048576, tag="memory_size_multi", width=200)
                    dpg.add_input_int(label="Acessos", default_value=10000, tag="acessos_multi", width=200)
                    dpg.add_input_int(label="N Simulações", default_value=10, tag="n_simulacoes_multi", width=200)
                    
                    dpg.add_separator()
                    dpg.add_text("Configuração Cache L1")
                    dpg.add_input_int(label="Tamanho Cache L1 (Bytes)", default_value=8192, tag="tamanho_cache_l1", width=200)
                    dpg.add_input_int(label="Associatividade L1", default_value=16, tag="associatividade_l1", width=200)
                    dpg.add_combo(items=["FIFO", "LRU", "LFU", "Random"], default_value='LRU', label="Algoritmo L1", width=200, tag="algoritmo_l1")
                    dpg.add_input_int(label="Tempo Acesso L1 (ns)", default_value=1, tag="tempo_l1", width=200)
                    
                    dpg.add_separator()
                    dpg.add_checkbox(label="Usar Cache L2", default_value=True, tag="usar_l2")
                    dpg.add_text("Configuração Cache L2")
                    dpg.add_input_int(label="Tamanho Cache L2 (Bytes)", default_value=32768, tag="tamanho_cache_l2", width=200)
                    dpg.add_input_int(label="Associatividade L2", default_value=8, tag="associatividade_l2", width=200)
                    dpg.add_combo(items=["FIFO", "LRU", "LFU", "Random"], default_value='FIFO', label="Algoritmo L2", width=200, tag="algoritmo_l2")
                    dpg.add_input_int(label="Tempo Acesso L2 (ns)", default_value=5, tag="tempo_l2", width=200)
                    
                    dpg.add_separator()
                    dpg.add_checkbox(label="Usar Cache L3", default_value=False, tag="usar_l3")
                    dpg.add_text("Configuração Cache L3")
                    dpg.add_input_int(label="Tamanho Cache L3 (Bytes)", default_value=262144, tag="tamanho_cache_l3", width=200)
                    dpg.add_input_int(label="Associatividade L3", default_value=16, tag="associatividade_l3", width=200)
                    dpg.add_combo(items=["FIFO", "LRU", "LFU", "Random"], default_value='LRU', label="Algoritmo L3", width=200, tag="algoritmo_l3")
                    dpg.add_input_int(label="Tempo Acesso L3 (ns)", default_value=20, tag="tempo_l3", width=200)
                    
                    dpg.add_separator()
                    dpg.add_text("Configuração Memória Principal")
                    dpg.add_input_int(label="Tempo Acesso RAM (ns)", default_value=100, tag="tempo_ram", width=200)
                    
                    dpg.add_separator()
                    dpg.add_input_float(label="Probabilidade Temporal", default_value=0.2, tag="prob_temporal_multi", width=200)
                    dpg.add_input_float(label="Probabilidade Espacial", default_value=0.2, tag="prob_espacial_multi", width=200)
                    dpg.add_input_float(label="Probabilidade Região Quente", default_value=0.4, tag="prob_quente_multi", width=200)
                    
                    dpg.add_separator()
                    dpg.add_input_int(label="Tamanho do Bloco", default_value=64, tag="bloco_multi", width=200)

            dpg.add_separator()

            with dpg.group(horizontal=True):
                dpg.add_button(label="Simular", callback=rodar_simulacao_callback)
                dpg.add_button(label="Simular Multinível", callback=rodar_simulacao_multinivel_callback)
                dpg.add_button(label="Limpar Último", callback=limpar_ultimo_plot)
                dpg.add_button(label="Limpar Plots", callback=limpar_plots)
                dpg.add_button(label="Gerar Heatmap", callback=mapa_temporal_blocos)
                dpg.add_button(label="Limpar Heatmap", callback=limpar_heatmap)
                dpg.add_button(label="Sair", callback=close_callback)  # Botão manual para sair
                dpg.add_progress_bar(tag="barra", default_value=0.0, width=300)
                dpg.add_text("0% concluído", tag="texto")
                dpg.add_combo(items=["FIFO", "LRU", "LFU", "Random"], default_value='FIFO', label="<-- Algoritmo de Substituição", width=100, tag="combo_algoritmo",callback=selecionar_algoritmo)
            
            dpg.add_separator()
            dpg.add_input_text(label="<-- Resultado da Última Simulação", multiline=True, readonly=True, height=35, tag="resultados_box")
            
            dpg.add_separator()
            dpg.add_text("", tag="mensagem_erro")
            dpg.add_separator()

            with dpg.group(horizontal=True):
                with dpg.plot(label="Taxa de acerto vs Tamanho do Bloco", tag="plot", height=380, width=600):
                    dpg.add_plot_legend()
                    x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Tamanho do Bloco", tag="x_axis")
                    y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Taxa de Acerto", tag="y_axis")
                dpg.add_input_text(label="<-- Resumo da Simulação", multiline=True, readonly=True, height=380, width=360, default_value="", tag="Resumo")
                
                with dpg.group(tag="heatmap_group"):
                    dpg.add_text("Mapa de Calor dos Acessos à Memória")

        # Configuração do viewport para ocupar 100% da tela
        dpg.create_viewport(title='Simulação de Cache')
        
        # Define a janela como janela primária (ocupa todo o viewport)
        dpg.set_primary_window("Primary Window", True)
        
        dpg.setup_dearpygui()
        
        # Maximiza automaticamente para ocupar toda a tela
        dpg.maximize_viewport()
        dpg.show_viewport()
        
        # Só redireciona stdout DEPOIS da interface estar pronta
        sys.stdout = DPGRedirector("Resumo")
        
        # Loop principal com verificação manual de fechamento
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        
        # Limpeza final ao sair do loop principal
        cleanup_on_exit()
        
    except Exception as e:
        # Garante que stdout seja restaurado antes de imprimir erro
        if hasattr(sys, '__stdout__'):
            sys.stdout = sys.__stdout__
        print(f"Erro na aplicação: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Garante que o contexto seja sempre destruído
        try:
            if dpg.does_context_exist():
                dpg.destroy_context()
        except:
            pass
        
        # Restaura stdout original
        try:
            sys.stdout = sys.__stdout__
        except:
            pass
        
        print("Aplicação finalizada com segurança.")
