from screeninfo import get_monitors
import os
def get_principal_monitor() -> tuple:
    """
    A função retorna a dimensão da tela principal.
    Retorna: (largura, altura)
    """
    monitors = get_monitors()
    for monitor in monitors:
        if monitor.is_primary:
            return (monitor.width, monitor.height)

def create_dir():
    # Define o nome da subpasta
    subpasta = "heatmaps"
    # Cria a subpasta se não existir
    os.makedirs(subpasta, exist_ok=True)

    #deleta todas as imagens da pasta
    for f in os.listdir(subpasta):
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
            os.remove(os.path.join(subpasta, f))


def criar_markdown_com_imagens_da_pasta(
    nome_arquivo="README.md",
    titulo="Simulação de Cache",
    descricao="Simulação de Cache",
    descricao_imagens = []
    ,
    pasta_imagens="heatmaps",
    autor="Pedro Henrique Bezerra de mello"
):
    

    # Lista todos os arquivos de imagem na subpasta
    extensoes_validas = (".png", ".jpg", ".jpeg", ".gif", ".bmp")
    imagens = [
        os.path.join(pasta_imagens, f)
        for f in os.listdir(pasta_imagens)
        if f.lower().endswith(extensoes_validas)
    ]

    conteudo_md = f"# Projeto de {titulo}\n\n"
    conteudo_md += f"## {titulo}\n\n"
    conteudo_md += f"{descricao}\n\n"

    

    if imagens:
        conteudo_md += "### Imagens Geradas\n"
        for i, imagem in enumerate(imagens, start=0):
            conteudo_md += f"![Imagem {i+1}]({imagem.split("\\")[-1]})\n"
            conteudo_md += "\n INFORMAÇÃO DA IMAGEM:\n"
            conteudo_md += f"Número de blocos - {descricao_imagens[i]['num_blocos']}\n"
            

            

    conteudo_md += "\n---\n\n"
    conteudo_md += f"Autor: {autor}"

    with open(f"heatmaps/{nome_arquivo}", "w", encoding="utf-8") as f:
        f.write(conteudo_md,)

    print(f"{nome_arquivo} criado com sucesso com {len(imagens)} imagem(ns).")
        
