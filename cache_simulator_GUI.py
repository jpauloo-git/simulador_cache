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
from screeninfo import get_monitors
from tools.getScreenInfo import get_principal_monitor
from tools.getScreenInfo import criar_markdown_com_imagens_da_pasta, create_dir

# Variáveis globais para configuração
algoritmo_escolhido = "FIFO"  # Algoritmo de substituição selecionado para cache de nível único

# Variáveis globais para configuração de cache multinível
modo_cache_multinivel = False  # Flag para indicar se está usando cache multinível
niveis_cache = []  # Lista de tuplas (cache_lines, associatividade, tempo_acesso)
algoritmos_por_nivel = []  # Algoritmos de substituição para cada nível

# Lista global para armazenar tags de séries de plotagem (caso visualizações sejam usadas)
plot_series_tags = []

# Variável global para armazenar resultados das simulações
resultados = []

# ------------------------------------------------------------------------------
# Redirecionador de saída padrão (print) para uma tag do DearPyGUI

class DPGRedirector:
    def __init__(self, tag):
        self.tag = tag
        self.buffer = ""

    def write(self, text):
        self.buffer += text
        current_text = dpg.get_value(self.tag)
        dpg.set_value(self.tag, current_text + text)

    def flush(self):
        pass  # Método necessário para compatibilidade com sys.stdout

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

        # Cópia do conjunto para o log
        conjunto_log.append(conjunto.copy())

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
# Callback para seleção do algoritmo via GUI
def selecionar_algoritmo(sender, app_data):
    global algoritmo_escolhido
    algoritmo_escolhido = app_data

# ------------------------------------------------------------------------------
# Geração de mapa de calor (heatmap) dos acessos por bloco ao longo do tempo
def mapa_temporal_blocos(padrao_acesso, memory_size, bloco_tamanho, resolucao_temporal=100):
    
    
    num_janelas = len(padrao_acesso) // resolucao_temporal
    num_blocos = memory_size // bloco_tamanho
    heatmap = np.zeros((num_blocos, num_janelas), dtype=int)

    for i, endereco in enumerate(padrao_acesso):
        tempo = i // resolucao_temporal
        bloco = endereco // bloco_tamanho
        if bloco < num_blocos and tempo < num_janelas:
            heatmap[bloco][tempo] += 1

    print(len(heatmap))
    print(heatmap)
    
    print('entramos na function')
    plt.figure(figsize=(10, 4))
    plt.imshow(heatmap, cmap='hot', aspect='auto', origin='lower')
    plt.colorbar(label="Número de acessos por bloco")
    plt.title("Evolução dos Acessos à Memória por Bloco")
    plt.xlabel(f"Grupos de {resolucao_temporal} Acessos")
    plt.ylabel("Bloco de Memória")
    plt.savefig(f"heatmaps/heatmap_{bloco_tamanho}.png")
    

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

    
    print(f'padrao: {padrao}')
    print(bloco_tamanho)
    print(memory_size)
    mapa_temporal_blocos(padrao, memory_size, bloco_tamanho, resolucao_temporal=100)

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
    create_dir()
    start_time = time.time()
    global resultados, niveis_cache, algoritmos_por_nivel, modo_cache_multinivel
    dpg.set_value("mensagem_erro", "")  # Limpa mensagem antiga
    
    try:
        # Leitura dos valores comuns (usados em ambos os modos)
        descricao_imagens = []
        memory_size = dpg.get_value("memory_size")
        acessos = dpg.get_value("acessos")
        n_simulacoes = dpg.get_value("n_simulacoes")
        prob_temporal = dpg.get_value("prob_temporal")
        prob_espacial = dpg.get_value("prob_espacial")
        prob_quente = dpg.get_value("prob_quente")
        
        regioes_quentes = [
            64, 1024, 8192, 32768, 131072, 262144, 524288, 786432, 983040
        ]

        # Verificações comuns
        if not (2**20 <= memory_size <= 2**30) or (memory_size & (memory_size-1)) != 0:
            dpg.set_value("mensagem_erro", "Erro: Memory Size deve ser potência de 2 entre 2^20 e 2^30.")
            return

        if not (0 <= prob_temporal <= 1) or not (0 <= prob_espacial <= 1) or not (0 <= prob_quente <= 1):
            dpg.set_value("mensagem_erro", "Erro: Probabilidades devem ser entre 0 e 1.")
            return

        resultados.clear()
        contador_barra = 0
        progresso = 0.01		# Mostra um andamento mínimo na barra de progresso para indicar que a nova simulação iniciou
        dpg.set_value("barra", progresso)
        dpg.set_value("texto", "Simulação Iniciada")
        
        # Modo Cache Multinível
        if modo_cache_multinivel:
            print(f"            ---   Simulação Cache Multinível ---\n")
            
            # Verificação específica para cache multinível
            if len(niveis_cache) == 0:
                dpg.set_value("mensagem_erro", "Erro: Configure pelo menos um nível de cache.")
                return
            
            bloco_tamanho = dpg.get_value("bloco_tamanho_multinivel")
            blocos = [bloco_tamanho]
            
            if bloco_tamanho <= 0 or bloco_tamanho >= memory_size or not is_power_of_two(bloco_tamanho):
                dpg.set_value("mensagem_erro", f"Tamanho do Bloco deve ser potência de 2 e menor que Memory Size. Valor fornecido: {bloco_tamanho}")
                return
            
            # Executa a simulação de cache multinível
            taxas_acerto_multi, tempo_medio = simulacao_monte_carlo_multinivel(
                n_simulacoes,
                acessos,
                memory_size,
                niveis_cache,
                algoritmos_por_nivel,
                regioes_quentes,
                (prob_temporal, prob_espacial, prob_quente),
                bloco_tamanho
            )
            
            descricao_imagens.append({"num_blocos": bloco_tamanho})
            dpg.set_value("barra", 1.0)
            dpg.set_value("texto", "100% concluído")
            
            # Preparar resultados para exibição
            texto = "Simulação de Cache Multinível\n"
            texto += f"Tamanho do Bloco: {bloco_tamanho} bytes\n"
            for i, taxa in enumerate(taxas_acerto_multi):
                texto += f"Nível L{i+1}: Taxa de Acerto = {taxa:.6f}\n"
                resultados.append((i+1, taxa))  # Para o gráfico: (nível, taxa)
            
            texto += f"Tempo Médio de Acesso: {tempo_medio:.2f} ns"
            dpg.set_value("resultados_box", texto)
            
            # Atualiza o plot
            atualizar_plot_multinivel()
            
            # Salva os resultados em CSV
            subpasta = "Resultados da Simulacao"
            os.makedirs(subpasta, exist_ok=True)
            agora = datetime.now()
            timestamp = agora.strftime("%Y-%m-%d_%H-%M-%S")
            nome_arquivo = f"Resultados da Simulacao - {timestamp}.csv"
            caminho_arquivo = os.path.join(subpasta, nome_arquivo)
            
            with open(caminho_arquivo, "w") as f:
                f.write(f"- Simulação Cache Multinível\n- Acessos = {acessos}\n- Bloco = {bloco_tamanho}\n- P_tem = {prob_temporal}\n- P_espa = {prob_espacial}\n- P_reg_quente = {prob_quente}\n\n")
                
                f.write("Nível,Tamanho Cache,Associatividade,Tempo Acesso,Algoritmo,Taxa Acerto\n")
                for i, taxa in enumerate(taxas_acerto_multi):
                    cache_lines, associatividade, tempo_acesso = niveis_cache[i]
                    algoritmo = algoritmos_por_nivel[i]
                    tamanho_cache = cache_lines * bloco_tamanho
                    f.write(f"L{i+1},{tamanho_cache},{associatividade},{tempo_acesso},{algoritmo},{taxa:.6f}\n")
                
                f.write(f"\nTempo Médio de Acesso,{tempo_medio:.2f} ns\n")
        
        # Modo Cache Normal (original)
        else:
            print(f"            ---   Algoritmo: {algoritmo_escolhido} ---\n")
            
            # Leitura dos valores específicos para modo normal
            tamanho_cache_bytes = dpg.get_value("tamanho_cache")
            associatividade = dpg.get_value("associatividade")
            blocos = dpg.get_value("blocos")
            blocos = [int(b.strip()) for b in blocos.split(",")]
            
            # Verificações específicas para o modo normal
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
            
            # Executa simulações para cada tamanho de bloco
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
                descricao_imagens.append({"num_blocos": bt})
                dpg.set_value("barra", progresso)
                dpg.set_value("texto", f"{int(progresso*100)}% concluído")
                resultados.append((bt, taxas_acerto))
                dpg.split_frame()  # Permite que a interface atualize
            
            # Atualiza o gráfico
            atualizar_plot()

            if resultados:
                tamanhos, taxas = zip(*resultados)
                texto = f"Tamanhos_de_bloco = [{', '.join(str(int(t)) for t in tamanhos)}];\n"
                texto += f"Taxa_media_de_acerto = [{', '.join(f'{float(t):.6f}' for t in taxas)}];"
            
                # Atualiza o conteúdo da caixa de texto na interface
                dpg.set_value("resultados_box", texto)
            
                # Salva os resultados em um arquivo CSV
                subpasta = "Resultados da Simulacao"
                os.makedirs(subpasta, exist_ok=True)
                agora = datetime.now()
                timestamp = agora.strftime("%Y-%m-%d_%H-%M-%S")
                nome_arquivo = f"Resultados da Simulacao - {timestamp}.csv"
                caminho_arquivo = os.path.join(subpasta, nome_arquivo)
                with open(caminho_arquivo, "w") as f:
                    f.write(f"- Algoritmo = {algoritmo_escolhido}\n- Associatividade = {associatividade}\n- Acessos = {acessos}\n- Cache = {tamanho_cache_bytes}\n- P_tem = {prob_temporal}\n- P_espa = {prob_espacial}\n- P_reg_quente = {prob_quente}\n")
                    f.write("\nTamanho_Bloco,Taxa_Acerto\n")
                    for bloco, taxa in resultados:
                        f.write(f"{bloco},{taxa:.6f}\n")
        
        # Gerar Markdown com heatmaps (comum para ambos os modos)
        criar_markdown_com_imagens_da_pasta(
            nome_arquivo="Simulacao_Heatmap.md",
            titulo="Simulação de Cache - HEATMAP",
            descricao=f"Simulação de Cache - HEATMAP \n - {'Multinível' if modo_cache_multinivel else 'Algoritmo: ' + algoritmo_escolhido}\n- {'Níveis: ' + str(len(niveis_cache)) if modo_cache_multinivel else 'Associatividade = ' + str(associatividade)}\n- Acessos = {acessos}\n- P_tem = {prob_temporal}\n- P_espa = {prob_espacial}\n- P_reg_quente = {prob_quente}\n",
            descricao_imagens= descricao_imagens,
            autor="Simulador de Cache"
        )
    except Exception as e:
        dpg.set_value("mensagem_erro", f"Erro inesperado: {str(e)}")
    # Mede tempo de simulação:
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Tempo de execução: {elapsed_time:.2f} segundos\n")
    print("          ------------++-------------     \n")


# Limpa plots e elementos graficos (barra e caixas de texto)
def limpar_plots():
    global plot_series_tags
    plot_series_tags = []
    dpg.delete_item("y_axis", children_only=True)
    dpg.set_value("barra", 0.0)
    dpg.set_value("texto", f"0% concluído")
    dpg.set_value("Resumo", "\n")
    dpg.set_value("resultados_box", "\n")
    dpg.set_value("mensagem_erro", " ")

def limpar_ultimo_plot():
    global plot_series_tags
    # Limpa dados da simulação na Caixa de tetxto Resumo		        
    # dpg.set_value("Resumo", "\n")
    dpg.set_value("mensagem_erro", " ")
    dpg.set_value("barra", 0.0)
    dpg.set_value("texto", f"0% concluído")
    dpg.set_value("resultados_box", "\n")		
    if plot_series_tags:
        ultimo_tag = plot_series_tags.pop()
        dpg.delete_item(ultimo_tag)
        print(f"Apagado: {ultimo_tag}")

import math
def atualizar_plot():
    global plot_series_tags
    if not dpg.does_item_exist("y_axis"):
        print("Erro: 'y_axis' não existe.")
        return

    # dpg.delete_item("plot_series", children_only=True)
    tamanhos, taxas = zip(*resultados)

    # Calcula log2 dos tamanhos
    tamanhos_log2 = [math.log2(tam) for tam in tamanhos]

    # Verifica consistência
    if len(tamanhos_log2) != len(taxas):
        print("Erro: tamanhos_log2 e taxas têm tamanhos diferentes")
        return

    # dpg.set_axis_limits("x_axis", min(tamanhos_log2), max(tamanhos_log2))
    # dpg.set_axis_limits("y_axis", min(taxas), max(taxas))
    plot_series = f"plot_{len(plot_series_tags)}"
    print(f"\nPlot Atual: {plot_series}\n")
    plot_series_tags.append(plot_series)
    dpg.add_line_series(
        tamanhos_log2,
        taxas,
        label=f"{algoritmo_escolhido}",
        parent="y_axis",
        tag=plot_series,
		show=True
    )
    dpg.fit_axis_data("x_axis")
    dpg.fit_axis_data("y_axis")
    dpg.set_item_label("plot", "Taxa de acerto vs Tamanho do Bloco")


# ------------------------------------------------------------------------------
# Simulação de cache multinível
def simular_cache_multinivel(padrao_acesso, niveis_cache, algoritmos, bloco_tamanho):
    """
    Simula o comportamento de uma hierarquia de cache multinível.
    
    Args:
        padrao_acesso: Lista de endereços de memória acessados
        niveis_cache: Lista de tuplas (cache_lines, associatividade, tempo_acesso) para cada nível
        algoritmos: Lista de algoritmos de substituição para cada nível ('FIFO', 'LRU', 'LFU', 'Random')
        bloco_tamanho: Tamanho do bloco de cache em bytes
    
    Returns:
        dict: Informações sobre hits/misses em cada nível e tempo médio de acesso
    """
    n_niveis = len(niveis_cache)
    hits_por_nivel = [0] * n_niveis
    misses_por_nivel = [0] * n_niveis
    hit_logs = [[] for _ in range(n_niveis)]
    
    # Lista de caches já inicializadas por nível
    caches = []
    for i in range(n_niveis):
        cache_lines, associatividade, _ = niveis_cache[i]
        num_conjuntos = cache_lines // associatividade
        
        # Inicializa o cache de acordo com o algoritmo escolhido
        if algoritmos[i] == 'FIFO':
            cache = [[] for _ in range(num_conjuntos)]
        elif algoritmos[i] == 'LRU':
            cache = [deque() for _ in range(num_conjuntos)]
        elif algoritmos[i] == 'LFU':
            cache = [{} for _ in range(num_conjuntos)]
        elif algoritmos[i] == 'Random':
            cache = [[] for _ in range(num_conjuntos)]
        else:
            raise ValueError(f"Algoritmo desconhecido: {algoritmos[i]}")
        
        caches.append(cache)
    
    # Simulação dos acessos
    for endereco in padrao_acesso:
        bloco = endereco // bloco_tamanho
        
        # Tenta acessar o bloco em cada nível de cache
        hit_em_nivel_anterior = False
        for nivel in range(n_niveis):
            if hit_em_nivel_anterior:
                # Se já acertamos em um nível anterior, contamos como hit automático
                hits_por_nivel[nivel] += 1
                hit_logs[nivel].append(1)
                continue
            
            cache_lines, associatividade, _ = niveis_cache[nivel]
            num_conjuntos = cache_lines // associatividade
            conjunto = bloco % num_conjuntos
            cache_atual = caches[nivel]
            
            # Verifica se o bloco está no cache atual
            hit = False
            if algoritmos[nivel] == 'FIFO':
                conjunto_atual = cache_atual[conjunto]
                if bloco in conjunto_atual:
                    hit = True
                    hits_por_nivel[nivel] += 1
                    hit_logs[nivel].append(1)
                else:
                    misses_por_nivel[nivel] += 1
                    hit_logs[nivel].append(0)
                    if len(conjunto_atual) < associatividade:
                        conjunto_atual.append(bloco)
                    else:
                        conjunto_atual.pop(0)  # Remove o mais antigo
                        conjunto_atual.append(bloco)
            
            elif algoritmos[nivel] == 'LRU':
                conjunto_atual = cache_atual[conjunto]
                if bloco in conjunto_atual:
                    hit = True
                    hits_por_nivel[nivel] += 1
                    hit_logs[nivel].append(1)
                    conjunto_atual.remove(bloco)
                    conjunto_atual.append(bloco)
                else:
                    misses_por_nivel[nivel] += 1
                    hit_logs[nivel].append(0)
                    if len(conjunto_atual) >= associatividade:
                        conjunto_atual.popleft()
                    conjunto_atual.append(bloco)
            
            elif algoritmos[nivel] == 'LFU':
                conjunto_atual = cache_atual[conjunto]
                if bloco in conjunto_atual:
                    hit = True
                    hits_por_nivel[nivel] += 1
                    hit_logs[nivel].append(1)
                    conjunto_atual[bloco] += 1
                else:
                    misses_por_nivel[nivel] += 1
                    hit_logs[nivel].append(0)
                    if len(conjunto_atual) < associatividade:
                        conjunto_atual[bloco] = 1
                    else:
                        bloco_remover = min(conjunto_atual, key=conjunto_atual.get)
                        del conjunto_atual[bloco_remover]
                        conjunto_atual[bloco] = 1
            
            elif algoritmos[nivel] == 'Random':
                conjunto_atual = cache_atual[conjunto]
                if bloco in conjunto_atual:
                    hit = True
                    hits_por_nivel[nivel] += 1
                    hit_logs[nivel].append(1)
                else:
                    misses_por_nivel[nivel] += 1
                    hit_logs[nivel].append(0)
                    if len(conjunto_atual) < associatividade:
                        conjunto_atual.append(bloco)
                    else:
                        idx_remover = random.randint(0, associatividade - 1)
                        conjunto_atual[idx_remover] = bloco
            
            hit_em_nivel_anterior = hit
            
            # Se foi um hit em qualquer nível, propaga o bloco para os níveis superiores
            # (política de inclusão)
            if hit and nivel > 0:
                # Propaga o acesso para níveis de cache superiores
                for nivel_superior in range(nivel - 1, -1, -1):
                    cache_sup_lines, assoc_sup, _ = niveis_cache[nivel_superior]
                    num_conj_sup = cache_sup_lines // assoc_sup
                    conj_sup = bloco % num_conj_sup
                    cache_sup = caches[nivel_superior]
                    
                    # Adiciona o bloco nos níveis superiores seguindo o algoritmo correspondente
                    if algoritmos[nivel_superior] == 'FIFO':
                        conjunto_sup = cache_sup[conj_sup]
                        if bloco not in conjunto_sup:
                            if len(conjunto_sup) >= assoc_sup:
                                conjunto_sup.pop(0)
                            conjunto_sup.append(bloco)
                    
                    elif algoritmos[nivel_superior] == 'LRU':
                        conjunto_sup = cache_sup[conj_sup]
                        if bloco in conjunto_sup:
                            conjunto_sup.remove(bloco)
                        else:
                            if len(conjunto_sup) >= assoc_sup:
                                conjunto_sup.popleft()
                        conjunto_sup.append(bloco)
                    
                    elif algoritmos[nivel_superior] == 'LFU':
                        conjunto_sup = cache_sup[conj_sup]
                        if bloco not in conjunto_sup:
                            if len(conjunto_sup) >= assoc_sup:
                                bloco_remover = min(conjunto_sup, key=conjunto_sup.get)
                                del conjunto_sup[bloco_remover]
                            conjunto_sup[bloco] = 1
                        else:
                            conjunto_sup[bloco] += 1
                    
                    elif algoritmos[nivel_superior] == 'Random':
                        conjunto_sup = cache_sup[conj_sup]
                        if bloco not in conjunto_sup:
                            if len(conjunto_sup) >= assoc_sup:
                                idx_remover = random.randint(0, assoc_sup - 1)
                                conjunto_sup[idx_remover] = bloco
                            else:
                                conjunto_sup.append(bloco)
    
    # Calcula as estatísticas
    taxa_acerto_por_nivel = []
    for nivel in range(n_niveis):
        total_acessos = hits_por_nivel[nivel] + misses_por_nivel[nivel]
        taxa_acerto = hits_por_nivel[nivel] / total_acessos if total_acessos > 0 else 0
        taxa_acerto_por_nivel.append(taxa_acerto)
    
    # Calcula o tempo médio de acesso usando a fórmula Tmed
    tempo_medio = 0
    probabilidades = []
    
    # Primeiro calcula as probabilidades de acerto em cada nível
    p_acerto_l1 = taxa_acerto_por_nivel[0]
    probabilidades.append(p_acerto_l1)
    
    probabilidade_acumulada = p_acerto_l1
    for nivel in range(1, n_niveis):
        # Probabilidade condicional de acertar neste nível dado que erramos em todos os níveis anteriores
        p_acerto_nivel = taxa_acerto_por_nivel[nivel]
        p_condicional = p_acerto_nivel * (1 - probabilidade_acumulada)
        probabilidades.append(p_condicional)
        probabilidade_acumulada += p_condicional
    
    # Probabilidade de ir até a memória principal
    p_memoria = 1 - probabilidade_acumulada
    probabilidades.append(p_memoria)
    
    # Calcula o tempo médio usando a fórmula Tmed
    for nivel in range(n_niveis):
        tempo_acesso = niveis_cache[nivel][2]  # Tempo de acesso para este nível
        tempo_medio += probabilidades[nivel] * tempo_acesso
    
    # Adiciona o tempo da memória principal (último elemento)
    tempo_memoria = niveis_cache[-1][2] * 5  # Assumimos que a memória principal é 5x mais lenta que o último nível
    tempo_medio += probabilidades[-1] * tempo_memoria
    
    # Resultados
    resultados = {
        'hits_por_nivel': hits_por_nivel,
        'misses_por_nivel': misses_por_nivel,
        'taxa_acerto_por_nivel': taxa_acerto_por_nivel,
        'probabilidades': probabilidades,
        'tempo_medio': tempo_medio,
        'hit_logs': hit_logs
    }
    
    return resultados

# ------------------------------------------------------------------------------
# Simulação Monte Carlo para cache multinível
def simulacao_monte_carlo_multinivel(n_simulacoes, acessos, memory_size, niveis_cache, algoritmos, regioes_quentes, probs, bloco_tamanho):
    taxas_acerto_por_nivel = [[] for _ in range(len(niveis_cache))]
    tempos_medios = []
    
    for _ in range(n_simulacoes):
        padrao = gerar_padrao_realista(acessos, memory_size, regioes_quentes, *probs, bloco_tamanho)
        resultados = simular_cache_multinivel(padrao, niveis_cache, algoritmos, bloco_tamanho)
        
        # Armazena as taxas de acerto para cada nível
        for nivel, taxa in enumerate(resultados['taxa_acerto_por_nivel']):
            taxas_acerto_por_nivel[nivel].append(taxa)
        
        # Armazena o tempo médio de acesso
        tempos_medios.append(resultados['tempo_medio'])
    
    # Calcula médias
    taxas_medias = [np.mean(taxas) for taxas in taxas_acerto_por_nivel]
    tempo_medio_global = np.mean(tempos_medios)
    
    # Exibe estatísticas gerais
    print(f"--- Resultados para Cache Multinível: {acessos} Acessos - Bloco de {bloco_tamanho} ---\n")
    for nivel, taxa_media in enumerate(taxas_medias):
        print(f"Nível L{nivel+1} - Média da Taxa de Acerto: {taxa_media:.4f}")
    
    print(f"Tempo Médio de Acesso: {tempo_medio_global:.2f} ns")
    
    return taxas_medias, tempo_medio_global

# ------------------------------------------------------------------------------
# Funções de manipulação da interface para cache multinível
def atualizar_modo_cache(sender, app_data):
    global modo_cache_multinivel
    modo_cache_multinivel = app_data
    # Atualiza a visibilidade dos controles de configuração de cache multinível
    if modo_cache_multinivel:
        dpg.show_item("grupo_cache_multinivel")
        dpg.hide_item("grupo_cache_normal")
    else:
        dpg.hide_item("grupo_cache_multinivel")
        dpg.show_item("grupo_cache_normal")

def adicionar_nivel_cache():
    global niveis_cache, algoritmos_por_nivel
    tamanho = dpg.get_value("novo_nivel_tamanho")
    associatividade = dpg.get_value("novo_nivel_associatividade") 
    tempo_acesso = dpg.get_value("novo_nivel_tempo_acesso")
    algoritmo = dpg.get_value("novo_nivel_algoritmo")
    
    # Valida os valores
    if not (tamanho > 0 and is_power_of_two(tamanho)):
        dpg.set_value("mensagem_erro", "Erro: Tamanho de cache deve ser potência de 2 maior que zero.")
        return
    if not (associatividade > 0 and is_power_of_two(associatividade)):
        dpg.set_value("mensagem_erro", "Erro: Associatividade deve ser potência de 2 maior que zero.")
        return
    if not (tempo_acesso > 0):
        dpg.set_value("mensagem_erro", "Erro: Tempo de acesso deve ser maior que zero.")
        return
    
    # Adiciona o nível de cache
    nivel_atual = len(niveis_cache) + 1
    niveis_cache.append((tamanho // dpg.get_value("bloco_tamanho_multinivel"), associatividade, tempo_acesso))
    algoritmos_por_nivel.append(algoritmo)
    
    # Atualiza o texto de níveis configurados
    texto_atual = dpg.get_value("texto_niveis_cache")
    novo_texto = f"{texto_atual}\nL{nivel_atual}: {tamanho} bytes, {associatividade}-way, {tempo_acesso} ns, {algoritmo}"
    dpg.set_value("texto_niveis_cache", novo_texto)
    
    # Limpa os campos
    dpg.set_value("novo_nivel_tamanho", 8192)
    dpg.set_value("novo_nivel_associatividade", 2)
    dpg.set_value("novo_nivel_tempo_acesso", 1.0)
    dpg.set_value("mensagem_erro", "")

def limpar_niveis_cache():
    global niveis_cache, algoritmos_por_nivel
    niveis_cache = []
    algoritmos_por_nivel = []
    dpg.set_value("texto_niveis_cache", "Níveis de cache configurados:")
    dpg.set_value("mensagem_erro", "")

def atualizar_plot_multinivel():
    global plot_series_tags
    if not dpg.does_item_exist("y_axis"):
        print("Erro: 'y_axis' não existe.")
        return

    # Converte os níveis para strings para exibição no gráfico
    niveis, taxas = zip(*resultados)
    niveis_str = [f"L{nivel}" for nivel in niveis]
    
    # Define plot para cache multinível
    plot_series = f"plot_{len(plot_series_tags)}"
    print(f"\nPlot Multinível Atual: {plot_series}\n")
    plot_series_tags.append(plot_series)
    
    # No gráfico multinível, o eixo x são os níveis de cache (L1, L2, L3...)
    dpg.add_bar_series(
        niveis_str,
        taxas,
        label="Taxa de Acerto por Nível",
        parent="y_axis",
        tag=plot_series,
        show=True
    )
    
    # Ajusta os eixos para exibir corretamente
    dpg.fit_axis_data("x_axis")
    dpg.fit_axis_data("y_axis")
    
    # Atualiza o título do gráfico
    dpg.set_item_label("plot", "Taxa de Acerto por Nível de Cache")

# ------------------------------------------------------------------------------
# Função principal e configuração da GUI
def main():
    monitor_info = get_principal_monitor()
    
    dpg.create_context()
    sys.stdout = DPGRedirector("Resumo")  # Redireciona todos os prints
    
    dpg.create_viewport(
        title='Simulação de Cache Multinível',
        resizable=True,
        width=monitor_info[0],
        height=monitor_info[1]
    )
    
    with dpg.window(label="Simulação de Cache", width=monitor_info[0], height=monitor_info[1]):
        # Configurações comuns para ambos os modos
        with dpg.group(horizontal=True):
            dpg.add_checkbox(label="Usar Cache Multinível", callback=atualizar_modo_cache, default_value=False)
            dpg.add_text("- Selecione para habilitar a simulação de cache multinível")
        
        dpg.add_input_int(label="Memory Size", default_value=1048576, tag="memory_size", width=200)
        dpg.add_input_int(label="Acessos", default_value=10000, tag="acessos", width=200)
        dpg.add_input_int(label="N Simulações", default_value=10, tag="n_simulacoes", width=200)
        
        dpg.add_separator()
        dpg.add_input_float(label="Probabilidade Temporal", default_value=0.2, tag="prob_temporal", width=200)
        dpg.add_input_float(label="Probabilidade Espacial", default_value=0.2, tag="prob_espacial", width=200)
        dpg.add_input_float(label="Probabilidade Região Quente", default_value=0.4, tag="prob_quente", width=200)
        
        dpg.add_separator()
        
        # Grupo para configurações de cache normal (único nível)
        with dpg.group(tag="grupo_cache_normal"):
            dpg.add_input_int(label="Tamanho Cache (Bytes)", default_value=8192, tag="tamanho_cache", width=200)
            dpg.add_input_int(label="Associatividade", default_value=16, tag="associatividade", width=200)
            dpg.add_input_text(label="Tamanhos de Bloco", default_value="2,4,8,16,32,64,128,256,512", tag="blocos", width=400)
            # Combobox escolha do algoritmo de substituição
            dpg.add_combo(items=["FIFO", "LRU", "LFU", "Random"], default_value='FIFO', label="Algoritmo de Substituição", width=200, tag="combo_algoritmo", callback=selecionar_algoritmo)
        
        # Grupo para configurações de cache multinível
        with dpg.group(tag="grupo_cache_multinivel", show=False):
            dpg.add_input_int(label="Tamanho do Bloco", default_value=64, tag="bloco_tamanho_multinivel", width=200)
            
            dpg.add_separator()
            dpg.add_text("Configure os níveis de cache (L1, L2, L3, ...)", wrap=400)
            
            with dpg.group(horizontal=True):
                dpg.add_input_int(label="Tamanho Cache (Bytes)", default_value=8192, tag="novo_nivel_tamanho", width=150)
                dpg.add_input_int(label="Associatividade", default_value=2, tag="novo_nivel_associatividade", width=120)
                dpg.add_input_float(label="Tempo Acesso (ns)", default_value=1.0, tag="novo_nivel_tempo_acesso", width=140)
                dpg.add_combo(items=["FIFO", "LRU", "LFU", "Random"], default_value="FIFO", label="Algoritmo", tag="novo_nivel_algoritmo", width=120)
                dpg.add_button(label="Adicionar Nível", callback=adicionar_nivel_cache)
                dpg.add_button(label="Limpar Níveis", callback=limpar_niveis_cache)
            
            dpg.add_text("Níveis de cache configurados:", tag="texto_niveis_cache", wrap=400)
        
        dpg.add_separator()
        
        # Controles comuns
        with dpg.group(horizontal=True):  # Inicia um grupo horizontal
            dpg.add_button(label="Simular", callback=rodar_simulacao_callback)
            dpg.add_button(label="Limpar Último", callback=limpar_ultimo_plot)
            dpg.add_button(label="Limpar Plots", callback=limpar_plots)
            dpg.add_progress_bar(tag="barra", default_value=0.0, width=300)
            dpg.add_text("0% concluído", tag="texto")
        
        dpg.add_separator()
        dpg.add_input_text(label="<-- Resultado da Última Simulação", multiline=True, readonly=True, height=100, tag="resultados_box")
        
        dpg.add_separator()
        dpg.add_text("", tag="mensagem_erro")
        dpg.add_separator()
    
        with dpg.group(horizontal=True):  # Inicia um grupo horizontal
            with dpg.plot(label="Taxa de acerto vs Tamanho do Bloco", tag="plot", height=380, width=600):
                dpg.add_plot_legend()
                x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Tamanho do Bloco", tag="x_axis")
                y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Taxa de Acerto", tag="y_axis")
            dpg.add_input_text(label="<-- Resumo da Simulação", multiline=True, readonly=True, height=380, width=360, default_value="", tag="Resumo")
    
    dpg.setup_dearpygui()
    dpg.maximize_viewport()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == "__main__":
    main()
