import numpy as np
import matplotlib.pyplot as plt
import random
from collections import deque
import io
import base64
from PIL import Image
from io import BytesIO
import csv
import dearpygui.dearpygui as dpg
import time
import sys
from datetime import datetime
import os

# Classe que intercepta os print()s e envia para a input_text:
class DPGRedirector:
    def __init__(self, tag):
        self.tag = tag
        self.buffer = ""

    def write(self, text):
        self.buffer += text
        # Atualiza a interface sem apagar o que já existe
        current_text = dpg.get_value(self.tag)
        dpg.set_value(self.tag, current_text + text)

    def flush(self):
        pass  # Para compatibilidade com sys.stdout.flush()
		
plot_series_tags = []
# Funçoes de validação das entradas
def is_power_of_two(x):
    return (x != 0) and ((x & (x - 1)) == 0)


# --------------------------------------------------------------------------------------
def gerar_padrao_realista(acessos, memory_size, regioes_quentes, prob_temporal, prob_espacial, prob_quente, bloco_tamanho):
    padrao = []
    endereco_anterior = random.randint(0, memory_size - 1)
    for _ in range(acessos):
        r = random.random()
        if r < prob_temporal:
            endereco = endereco_anterior
        elif r < prob_temporal + prob_espacial:
            # deslocamento = random.randint(-bloco_tamanho // 4, bloco_tamanho // 4)
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
# --------------------------------------------------------------------------------------
# FIFO
def simular_cache_FIFO(padrao_acesso, cache_lines, associatividade, bloco_tamanho):
    
    num_conjuntos = cache_lines // associatividade
    cache = [[] for _ in range(num_conjuntos)]
    hits = 0
    misses = 0
    conjunto_log = []
    hit_log = []

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
                conjunto_atual.pop(0)
                conjunto_atual.append(bloco)

        conjunto_log.append(conjunto)

    return conjunto_log, hit_log

# FIFO com deque (deveria ser mais rápida, MAS, está mais lenta que a versão com dicionário
# def simular_cache_FIFO(padrao_acesso, cache_lines, associatividade, bloco_tamanho):
    # num_conjuntos = cache_lines // associatividade
    # cache = [deque() for _ in range(num_conjuntos)]  # Usando deque
    # hits = 0
    # misses = 0
    # conjunto_log = []
    # hit_log = []

    # for endereco in padrao_acesso:
        # bloco = endereco // bloco_tamanho
        # conjunto = bloco % num_conjuntos
        # conjunto_atual = cache[conjunto]

        # if bloco in conjunto_atual:
            # hits += 1
            # hit_log.append(1)
        # else:
            # misses += 1
            # hit_log.append(0)
            # if len(conjunto_atual) >= associatividade:
                # conjunto_atual.popleft()  # Remove o mais antigo (FIFO)
            # conjunto_atual.append(bloco)  # Adiciona o novo

        # conjunto_log.append(conjunto)

    # return conjunto_log, hit_log



# LRU
def simular_cache_LRU(padrao_acesso, cache_lines, associatividade, bloco_tamanho):
    num_conjuntos = cache_lines // associatividade
    cache = [deque() for _ in range(num_conjuntos)]
    hits = 0
    misses = 0
    conjunto_log = []
    hit_log = []

    for endereco in padrao_acesso:
        bloco = endereco // bloco_tamanho
        conjunto = bloco % num_conjuntos
        conjunto_atual = cache[conjunto]

        if bloco in conjunto_atual:
            hits += 1
            hit_log.append(1)
            conjunto_atual.remove(bloco)
            conjunto_atual.append(bloco)  # Move para o fim, como mais recentemente usado
        else:
            misses += 1
            hit_log.append(0)
            if len(conjunto_atual) >= associatividade:
                conjunto_atual.popleft()  # Remove o menos recentemente usado
            conjunto_atual.append(bloco)

        conjunto_log.append(conjunto)

    return conjunto_log, hit_log


def simular_cache_LFU(padrao_acesso, cache_lines, associatividade, bloco_tamanho):
    num_conjuntos = cache_lines // associatividade
    cache = [{} for _ in range(num_conjuntos)]  # Dicionário: bloco -> contador de uso
    hits = 0
    misses = 0
    conjunto_log = []
    hit_log = []

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
                # Remove o bloco menos frequentemente usado
                bloco_remover = min(conjunto_atual, key=conjunto_atual.get)
                del conjunto_atual[bloco_remover]
                conjunto_atual[bloco] = 1

        conjunto_log.append(conjunto)

    return conjunto_log, hit_log

import random
def simular_cache_RANDOM(padrao_acesso, cache_lines, associatividade, bloco_tamanho):
    num_conjuntos = cache_lines // associatividade
    cache = [[] for _ in range(num_conjuntos)]
    hits = 0
    misses = 0
    conjunto_log = []
    hit_log = []

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
# --------------------------------------------------------------------------------------
# Variável global para guardar o algoritmo selecionado
algoritmo_escolhido = "FIFO"
def selecionar_algoritmo(sender, app_data):
    global algoritmo_escolhido
    algoritmo_escolhido = app_data
    # dpg.set_value("algoritmo_texto", f"Selecionado: {algoritmo_escolhido}")

# --------------------------------------------------------------------------------------
def mapa_temporal_blocos(padrao_acesso, memory_size, bloco_tamanho, resolucao_temporal=100):
    num_janelas = len(padrao_acesso) // resolucao_temporal
    num_blocos = memory_size // bloco_tamanho
    heatmap = np.zeros((num_blocos, num_janelas), dtype=int)

    for i, endereco in enumerate(padrao_acesso):
        tempo = i // resolucao_temporal
        bloco = endereco // bloco_tamanho
        if bloco < num_blocos and tempo < num_janelas:
            heatmap[bloco][tempo] += 1

    plt.figure(figsize=(10, 4))
    plt.imshow(heatmap, cmap='hot', aspect='auto', origin='lower')
    plt.colorbar(label="Número de acessos por bloco")
    plt.title("Evolução dos Acessos à Memória por Bloco")
    mensagem = f"Grupos de {resolucao_temporal} Acessos"
    plt.xlabel(mensagem)
    plt.ylabel("Bloco de Memória")
    plt.show()
# --------------------------------------------------------------------------------------
def simulacao_monte_carlo(n_simulacoes, acessos, memory_size, cache_lines, associatividade, regioes_quentes, probs, bloco_tamanho):
    taxas_acerto = []
    hits_totais = []
    misses_totais = []

    for i in range(n_simulacoes):
        padrao = gerar_padrao_realista(acessos, memory_size, regioes_quentes, *probs, bloco_tamanho)
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
        taxas_acerto.append(taxa_acerto)
        hits_totais.append(hits)
        misses_totais.append(misses)

        # if i == 0:
            # mapa_temporal_blocos(padrao, memory_size, bloco_tamanho, resolucao_temporal=100)

    print(f"--- Resultados: {acessos} Acessos - Bloco de {bloco_tamanho} ---\n")
    print(f"Média da Taxa de Acerto: {np.mean(taxas_acerto):.4f}")
    print(f"Desvio padrão da Taxa de Acerto: {np.std(taxas_acerto):.4f}\n")   # print(f"Total médio de acessos: {acessos}")
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


# Interface
dpg.create_context()
sys.stdout = DPGRedirector("Resumo")  # Redireciona todos os prints

# Pega a resolução da tela
# viewport_width, viewport_height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()


with dpg.window(label="Simulação de Cache", width=1400, height=900):
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

    with dpg.group(horizontal=True):  # Inicia um grupo horizontal
        dpg.add_button(label="Simular", callback=rodar_simulacao_callback)
        dpg.add_button(label="Limpar Último", callback=limpar_ultimo_plot)
        dpg.add_button(label="Limpar Plots", callback= limpar_plots)
        dpg.add_progress_bar(tag="barra", default_value=0.0, width=300)
        dpg.add_text("0% concluído", tag="texto")
		# Combobox escolha do algoritmo de substituição
        # dpg.add_text("Algoritmo de Substituição:")		
        dpg.add_combo(items=["FIFO", "LRU", "LFU", "Random"], default_value='FIFO', label="<-- Algoritmo de Substituição", width=100, tag="combo_algoritmo",callback=selecionar_algoritmo)
        # Salvar Grafico está com erro!!!
        # dpg.add_button(label="Salvar Simulação", callback=export_callback)
        dpg.add_button(label="Mostrar Heatmap", callback=mapa_temporal_blocos)
    dpg.add_separator()
    dpg.add_input_text(label="<-- Resultado da Última Simulação", multiline=True, readonly=True, height=35, tag="resultados_box")
	
    dpg.add_separator()
    dpg.add_text("", tag="mensagem_erro")
    dpg.add_separator()

    with dpg.group(horizontal=True):  # Inicia um grupo horizontal
        with dpg.plot(label="Taxa de acerto vs Tamanho do Bloco", tag="plot", height=380, width=600):
            dpg.add_plot_legend()
            x_axis = dpg.add_plot_axis(dpg.mvXAxis, label="Tamanho do Bloco", tag="x_axis")
            y_axis = dpg.add_plot_axis(dpg.mvYAxis, label="Taxa de Acerto", tag="y_axis")
        dpg.add_input_text(label="<-- Resumo da Simulação", multiline=True, readonly=True, height=380, width=360, default_value="", tag="Resumo")


dpg.create_viewport(title='Simulação de Cache', width=800, height=600)
dpg.setup_dearpygui()
dpg.maximize_viewport()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()

