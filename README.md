# simulador_cache
Simulador de Memória Cache com Interface Gráfica (GUI)
Claro! Aqui está a versão revisada e formatada para o arquivo `README.md` de um repositório no GitHub. A linguagem foi ajustada para o estilo típico de documentação pública, mantendo clareza, objetividade e boa organização:

---

# Simulador de Memória Cache com Interface Gráfica (GUI)

## 1. Apresentação

Este simulador tem como objetivo didático auxiliar no estudo do comportamento de memórias cache em sistemas computacionais. Por meio de uma interface gráfica interativa (baseada em **Dear PyGui**), o usuário pode configurar diversos parâmetros da arquitetura de cache e do padrão de acesso à memória, observando o impacto nas taxas de acerto (*hit rate*) sob diferentes políticas de substituição.

## 2. Funcionalidades Principais

* Simulação de acessos à memória com padrões realistas baseados em:

  * Localidade temporal
  * Localidade espacial
  * Regiões quentes de memória
* Implementação das principais políticas de substituição:

  * **FIFO** (First-In First-Out)
  * **LRU** (Least Recently Used)
  * **LFU** (Least Frequently Used)
  * **Random**
* Geração de **mapa de calor (heatmap)** para visualização da frequência de acesso por bloco de memória ao longo do tempo **(desabilitado por erro no código)**.
* Execução de **simulações Monte Carlo** para análise estatística da taxa de acerto.
* Exibição dos resultados diretamente na interface, incluindo média e desvio padrão da taxa de acerto.

## 3. Parâmetros Ajustáveis pelo Usuário

O simulador permite a configuração dos seguintes parâmetros:

* Tamanho da memória principal (número de endereços)
* Quantidade de acessos simulados
* Número total de linhas da cache
* Grau de associatividade (linhas por conjunto)
* Tamanho do bloco (endereços por bloco)
* Número de regiões quentes (áreas mais frequentemente acessadas)
* Probabilidades associadas ao padrão de acesso:

  * Localidade temporal (repetição do último acesso)
  * Localidade espacial (endereços próximos ao anterior)
  * Regiões quentes (foco em áreas específicas)
* Política de substituição (FIFO, LRU, LFU, Random)
* Número de simulações (para Monte Carlo)

## 4. Geração do Padrão de Acesso

Os endereços são gerados com base em um modelo probabilístico que busca simular o comportamento real de programas:

* Uma fração repete o endereço anterior (*localidade temporal*)
* Outra fração acessa endereços vizinhos (*localidade espacial*)
* Outra parte concentra acessos em **regiões quentes**
* O restante realiza acessos aleatórios

## 5. Políticas de Substituição

Cada política é implementada com estruturas de dados apropriadas que refletem seu comportamento esperado:

### 5.1 FIFO

Remove o bloco mais antigo inserido no conjunto.

### 5.2 LRU

Remove o bloco **menos recentemente utilizado**.

### 5.3 LFU

Remove o bloco **menos frequentemente acessado**. A seguir, descreve-se a lógica da função de simulação `simular_cache_LFU`:

```python
def simular_cache_LFU(padrao_acesso, cache_lines, associatividade, bloco_tamanho):
```

* `padrao_acesso`: lista de endereços simulados.
* `cache_lines`: número total de linhas da cache.
* `associatividade`: número de linhas por conjunto.
* `bloco_tamanho`: quantidade de endereços por bloco.

**Etapas da Simulação**:

1. Calcula-se o número de conjuntos: `num_conjuntos = cache_lines // associatividade`
2. Inicializa-se a cache: `cache = [{} for _ in range(num_conjuntos)]`
3. Estatísticas: `hits`, `misses`, `hit_log`, `conjunto_log`
4. Para cada endereço:

   * Calcula-se `bloco = endereco // bloco_tamanho`
   * Determina-se o `conjunto = bloco % num_conjuntos`
   * Verifica-se HIT ou MISS
   * Atualiza-se o contador ou substitui o bloco menos acessado

**Retorno**:

* Lista de conjuntos acessados
* Lista binária de HIT/MISS

A política **LFU** mantém um contador para cada bloco e sempre remove o de menor valor.

### 5.4 Random

Seleciona um bloco aleatoriamente para substituição.

## 6. Saída e Resultados

Ao final da simulação, são apresentados:

* Taxa de acerto: `cache hits / total de acessos`
* Quando múltiplas simulações são realizadas:

  * Média e desvio padrão da taxa de acerto
  * Média e variância de hits e misses

Todos os resultados são exibidos diretamente na interface gráfica.

## 7. Visualização Gráfica (opcional)

A função `mapa_temporal_blocos` gera um **heatmap** com:

* Blocos de memória no eixo vertical
* Janelas temporais no eixo horizontal

Essa visualização facilita a identificação de padrões e regiões de maior atividade ao longo do tempo.

## 8. Requisitos

* Python 3.x
* Bibliotecas necessárias:

  * `numpy`
  * `matplotlib`
  * `dearpygui`
  * `collections`
  * `random`
  * `io`, `base64` (opcional)

## 9. Aplicações Didáticas

Este simulador pode ser utilizado em disciplinas como:

* Organização e Arquitetura de Computadores
* Sistemas Operacionais
* Sistemas Embarcados
* Simulação de Sistemas

É uma ferramenta prática para entender conceitos fundamentais de caches, localidade de acesso e impacto das políticas de substituição na performance.
