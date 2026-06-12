import os
import json
from pathlib import Path
from itertools import combinations
from collections import Counter, defaultdict

from PIL import Image

from utilitario.outros import replace_com_incremento, selecionar_arquivos


# ============================================================
# Configuração geral
# ============================================================

PNG_JSON_KEY = "peritask_mp4_atoms_tree_json"
PNG_SCHEMA = "peritask_mp4_atoms_tree_v1"

TIPOS_SAMPLE_VIDEO = {
    "avc1", "avc2", "avc3", "avc4",
    "hvc1", "hev1", "mp4v", "encv",
}

TIPOS_SAMPLE_AUDIO = {
    "mp4a", "enca", "alac", "ac-3", "ec-3", "Opus",
}


# ============================================================
# Leitura do JSON embutido no PNG
# ============================================================

def extrair_estrutura_json_do_png(caminho_png):
    """
    Recupera a estrutura JSON embutida no PNG.
    """
    with Image.open(caminho_png) as img:
        texto_json = img.info.get(PNG_JSON_KEY)

    if not texto_json:
        return None

    return json.loads(texto_json)


# ============================================================
# Normalização das árvores
# ============================================================

def obter_tree(estrutura):
    return estrutura.get("tree", [])


def assinatura_exata_nos(nos):
    """
    Assinatura exata:
    - tipo;
    - offset;
    - tamanho;
    - filhos.

    Se duas assinaturas forem iguais, as estruturas são exatamente iguais
    no nível registrado pelo PNG.
    """
    assinatura = []

    for no in nos:
        assinatura.append((
            no.get("type"),
            no.get("offset"),
            no.get("size"),
            tuple(assinatura_exata_nos(no.get("children", []))),
        ))

    return tuple(assinatura)


def assinatura_forma_nos(nos):
    """
    Assinatura estrutural:
    - tipo;
    - filhos.

    Ignora tamanhos e offsets. Útil para detectar mesma hierarquia
    com variação apenas de tamanho/offset.
    """
    assinatura = []

    for no in nos:
        assinatura.append((
            no.get("type"),
            tuple(assinatura_forma_nos(no.get("children", []))),
        ))

    return tuple(assinatura)


def assinatura_forma_no(no):
    return (
        no.get("type"),
        tuple(assinatura_forma_nos(no.get("children", []))),
    )


def assinatura_forma_sem_traks_nos(nos):
    """
    Assinatura estrutural ignorando subárvores 'trak'.

    Serve para verificar se todo o restante do arquivo bate,
    deixando as tracks para comparação específica.
    """
    assinatura = []

    for no in nos:
        tipo = no.get("type")

        if tipo == "trak":
            continue

        assinatura.append((
            tipo,
            tuple(assinatura_forma_sem_traks_nos(no.get("children", []))),
        ))

    return tuple(assinatura)


def listar_caminhos_tipos(nos, prefixo=""):
    """
    Lista caminhos hierárquicos por tipo para cálculo de similaridade.

    Usa multiset/counter para preservar repetições.
    """
    caminhos = []

    for no in nos:
        tipo = no.get("type")
        caminho = f"{prefixo}/{tipo}" if prefixo else f"/{tipo}"
        caminhos.append(caminho)

        caminhos.extend(
            listar_caminhos_tipos(
                no.get("children", []),
                caminho,
            )
        )

    return caminhos


def calcular_similaridade_estrutural(tree_a, tree_b):
    """
    Similaridade estrutural por multiconjunto de caminhos de tipos.

    Retorna valor entre 0 e 1.
    """
    caminhos_a = Counter(listar_caminhos_tipos(tree_a))
    caminhos_b = Counter(listar_caminhos_tipos(tree_b))

    if not caminhos_a and not caminhos_b:
        return 1.0

    intersecao = sum((caminhos_a & caminhos_b).values())
    uniao = sum((caminhos_a | caminhos_b).values())

    if uniao == 0:
        return 0.0

    return intersecao / uniao


# ============================================================
# Utilidades de árvore
# ============================================================

def encontrar_primeiro_no_por_tipo(nos, tipo_procurado):
    for no in nos:
        if no.get("type") == tipo_procurado:
            return no

        encontrado = encontrar_primeiro_no_por_tipo(
            no.get("children", []),
            tipo_procurado,
        )

        if encontrado:
            return encontrado

    return None


def encontrar_filhos_por_tipo(no, tipo_procurado):
    return [
        filho for filho in no.get("children", [])
        if filho.get("type") == tipo_procurado
    ]


def coletar_tipos_recursivo(no):
    tipos = []

    def visitar(atual):
        tipos.append(atual.get("type"))

        for filho in atual.get("children", []):
            visitar(filho)

    visitar(no)

    return tipos


def inferir_tipo_trak(trak):
    """
    Infere se uma trak parece ser de vídeo, áudio ou outro tipo
    a partir dos sample entries encontrados, como avc1, hvc1 e mp4a.
    """
    tipos = set(coletar_tipos_recursivo(trak))

    if tipos & TIPOS_SAMPLE_VIDEO:
        return "vídeo"

    if tipos & TIPOS_SAMPLE_AUDIO:
        return "áudio"

    return "tipo não identificado"


def resumir_trak(trak):
    tipo_trak = inferir_tipo_trak(trak)
    tamanho = trak.get("size")

    samples = []
    tipos = set(coletar_tipos_recursivo(trak))

    for tipo in sorted(tipos):
        if tipo in TIPOS_SAMPLE_VIDEO or tipo in TIPOS_SAMPLE_AUDIO:
            samples.append(tipo)

    if samples:
        return f"trak de {tipo_trak}, sample entry: {', '.join(samples)}, tamanho: {tamanho}"

    return f"trak de {tipo_trak}, tamanho: {tamanho}"


def obter_traks_do_moov(tree):
    moov = encontrar_primeiro_no_por_tipo(tree, "moov")

    if not moov:
        return []

    return encontrar_filhos_por_tipo(moov, "trak")


def remover_primeira_ocorrencia(lista, valor):
    """
    Remove a primeira ocorrência de 'valor' em uma lista, se existir.
    """
    nova = list(lista)

    try:
        nova.remove(valor)
    except ValueError:
        pass

    return nova


# ============================================================
# Diferenças para relatório
# ============================================================

def comparar_contadores(caminhos_a, caminhos_b, limite=12):
    """
    Retorna exemplos de caminhos ausentes/adicionais entre duas árvores.
    """
    counter_a = Counter(caminhos_a)
    counter_b = Counter(caminhos_b)

    apenas_a = counter_a - counter_b
    apenas_b = counter_b - counter_a

    exemplos_a = list(apenas_a.elements())[:limite]
    exemplos_b = list(apenas_b.elements())[:limite]

    return exemplos_a, exemplos_b


def detectar_derivacao_simples(tree_a, tree_b):
    """
    Detecta derivação simples.

    Critério aceito:
    - diferença explicável pela presença/ausência de uma ou mais 'trak'
      dentro de 'moov', mantendo o restante da estrutura compatível.

    Retorna:
    - (True, texto explicativo)
    - (False, texto explicativo)
    """
    sem_traks_a = assinatura_forma_sem_traks_nos(tree_a)
    sem_traks_b = assinatura_forma_sem_traks_nos(tree_b)

    if sem_traks_a != sem_traks_b:
        return False, "há diferenças estruturais fora de atoms trak"

    traks_a = obter_traks_do_moov(tree_a)
    traks_b = obter_traks_do_moov(tree_b)

    if not traks_a and not traks_b:
        return False, "não há diferença simples de tracks"

    assinaturas_a = [assinatura_forma_no(trak) for trak in traks_a]
    assinaturas_b = [assinatura_forma_no(trak) for trak in traks_b]

    restantes_b = list(assinaturas_b)
    traks_comuns = 0

    for assinatura_a in assinaturas_a:
        if assinatura_a in restantes_b:
            traks_comuns += 1
            restantes_b = remover_primeira_ocorrencia(restantes_b, assinatura_a)

    menor_quantidade = min(len(assinaturas_a), len(assinaturas_b))
    diferenca_quantidade = abs(len(assinaturas_a) - len(assinaturas_b))

    if traks_comuns == menor_quantidade and diferenca_quantidade > 0:
        if len(traks_a) > len(traks_b):
            extras = identificar_traks_extras(traks_a, traks_b)
            lado = "primeiro PNG"
        else:
            extras = identificar_traks_extras(traks_b, traks_a)
            lado = "segundo PNG"

        descricao_extras = "; ".join(resumir_trak(trak) for trak in extras)

        return True, (
            f"diferença explicável por {diferenca_quantidade} trak(s) "
            f"a mais no {lado}: {descricao_extras}"
        )

    return False, (
        "as tracks existentes não são apenas acréscimo/remoção simples; "
        "há mudança na estrutura interna de trak"
    )


def identificar_traks_extras(traks_maior, traks_menor):
    """
    Identifica tracks extras comparando assinaturas estruturais.
    """
    assinaturas_menor = [assinatura_forma_no(trak) for trak in traks_menor]

    extras = []

    for trak in traks_maior:
        assinatura = assinatura_forma_no(trak)

        if assinatura in assinaturas_menor:
            assinaturas_menor = remover_primeira_ocorrencia(
                assinaturas_menor,
                assinatura,
            )
        else:
            extras.append(trak)

    return extras


def classificar_par(estrutura_a, estrutura_b):
    """
    Classifica a comparação entre dois PNGs.

    Classes possíveis:
    - EXATAMENTE IGUAIS
    - IGUAIS
    - DERIVAÇÃO SIMPLES
    - DIFERENTES
    """
    tree_a = obter_tree(estrutura_a)
    tree_b = obter_tree(estrutura_b)

    assinatura_exata_a = assinatura_exata_nos(tree_a)
    assinatura_exata_b = assinatura_exata_nos(tree_b)

    forma_a = assinatura_forma_nos(tree_a)
    forma_b = assinatura_forma_nos(tree_b)

    similaridade = calcular_similaridade_estrutural(tree_a, tree_b)

    if assinatura_exata_a == assinatura_exata_b:
        return {
            "classe": "EXATAMENTE IGUAIS",
            "similaridade": similaridade,
            "detalhe": "mesma hierarquia de atoms, mesmos tamanhos e mesmos offsets registrados",
        }

    if forma_a == forma_b:
        return {
            "classe": "IGUAIS",
            "similaridade": similaridade,
            "detalhe": "mesma estrutura de atoms, divergindo apenas em tamanhos e/ou offsets registrados",
        }

    eh_derivacao, detalhe_derivacao = detectar_derivacao_simples(
        tree_a,
        tree_b,
    )

    if eh_derivacao:
        return {
            "classe": "DERIVAÇÃO SIMPLES",
            "similaridade": similaridade,
            "detalhe": detalhe_derivacao,
        }

    caminhos_a = listar_caminhos_tipos(tree_a)
    caminhos_b = listar_caminhos_tipos(tree_b)
    apenas_a, apenas_b = comparar_contadores(caminhos_a, caminhos_b)

    detalhe = (
        f"similaridade estrutural aproximada de {similaridade:.1%}; "
        "há diferenças não explicadas por igualdade estrutural ou derivação simples"
    )

    if apenas_a:
        detalhe += (
            f"; exemplos presentes apenas no primeiro PNG: "
            f"{', '.join(apenas_a)}"
        )

    if apenas_b:
        detalhe += (
            f"; exemplos presentes apenas no segundo PNG: "
            f"{', '.join(apenas_b)}"
        )

    return {
        "classe": "DIFERENTES",
        "similaridade": similaridade,
        "detalhe": detalhe,
    }


# ============================================================
# Agrupamentos para o resumo
# ============================================================

def nome_png(registro):
    return Path(registro["png"]).name


def ordenar_caminhos(caminhos):
    return sorted(caminhos, key=lambda p: Path(p).name.lower())


def agrupar_registros_por_assinatura(registros, funcao_assinatura):
    grupos_dict = defaultdict(list)

    for registro in registros:
        tree = obter_tree(registro["estrutura"])
        assinatura = funcao_assinatura(tree)
        grupos_dict[assinatura].append(registro)

    return [
        grupo for grupo in grupos_dict.values()
        if len(grupo) >= 2
    ]


def obter_mapa_grupo_por_caminho(grupos):
    mapa = {}

    for indice, grupo in enumerate(grupos, start=1):
        for registro in grupo:
            mapa[registro["png"]] = indice

    return mapa


def montar_resumo_derivacoes(resultados_pares, grupos_iguais):
    """
    Monta resumo de derivação simples sem repetir todo o grupo base.

    Exemplo esperado:
    Grupo 1:
    Base: Grupo 1 de IGUAIS
    Derivação simples:
    - atoms_VIDEO CAPTURA TELA INSTAGRAM_mp4.png
    """
    mapa_igual = obter_mapa_grupo_por_caminho(grupos_iguais)
    arquivos_iguais = set(mapa_igual.keys())

    derivacoes_por_grupo = defaultdict(set)
    derivacoes_sem_base = set()

    for resultado in resultados_pares:
        if resultado["classe"] != "DERIVAÇÃO SIMPLES":
            continue

        a = resultado["png_a"]
        b = resultado["png_b"]

        a_em_igual = a in arquivos_iguais
        b_em_igual = b in arquivos_iguais

        if a_em_igual and not b_em_igual:
            derivacoes_por_grupo[mapa_igual[a]].add(b)
        elif b_em_igual and not a_em_igual:
            derivacoes_por_grupo[mapa_igual[b]].add(a)
        elif a_em_igual and b_em_igual:
            continue
        else:
            derivacoes_sem_base.add(a)
            derivacoes_sem_base.add(b)

    return derivacoes_por_grupo, derivacoes_sem_base


def montar_resumo_diferentes(resultados_pares, grupos_iguais, derivacoes_por_grupo, derivacoes_sem_base):
    """
    Monta resumo de arquivos diferentes evitando listar o Grupo 1 inteiro.

    Se um arquivo for diferente de vários membros do mesmo grupo, o relatório
    menciona apenas que ele difere daquele grupo.
    """
    mapa_igual = obter_mapa_grupo_por_caminho(grupos_iguais)
    arquivos_iguais = set(mapa_igual.keys())

    mapa_derivacao = {}

    for indice_grupo, arquivos_derivados in derivacoes_por_grupo.items():
        for arquivo in arquivos_derivados:
            mapa_derivacao[arquivo] = indice_grupo

    for arquivo in derivacoes_sem_base:
        mapa_derivacao[arquivo] = None

    candidatos = set()

    for resultado in resultados_pares:
        if resultado["classe"] != "DIFERENTES":
            continue

        a = resultado["png_a"]
        b = resultado["png_b"]

        if a not in arquivos_iguais and a not in mapa_derivacao:
            candidatos.add(a)

        if b not in arquivos_iguais and b not in mapa_derivacao:
            candidatos.add(b)

    resumo = []

    for candidato in ordenar_caminhos(candidatos):
        difere_de = set()

        for resultado in resultados_pares:
            if resultado["classe"] != "DIFERENTES":
                continue

            a = resultado["png_a"]
            b = resultado["png_b"]

            if candidato == a:
                outro = b
            elif candidato == b:
                outro = a
            else:
                continue

            if outro in arquivos_iguais:
                difere_de.add(f"Grupo {mapa_igual[outro]} de IGUAIS")
            elif outro in mapa_derivacao:
                indice_derivacao = mapa_derivacao[outro]

                if indice_derivacao is None:
                    difere_de.add(Path(outro).name)
                else:
                    difere_de.add(f"derivação simples do Grupo {indice_derivacao}")
            else:
                difere_de.add(Path(outro).name)

        resumo.append({
            "arquivo": candidato,
            "difere_de": sorted(difere_de),
        })

    return resumo


def escrever_grupos_de_registros(linhas, grupos):
    if not grupos:
        linhas.append("- Nenhum.")
        return

    for indice, grupo in enumerate(grupos, start=1):
        linhas.append(f"Grupo {indice}:")

        for registro in sorted(grupo, key=lambda r: nome_png(r).lower()):
            linhas.append(f"- {nome_png(registro)}")


def escrever_resumo_derivacoes(linhas, derivacoes_por_grupo, derivacoes_sem_base):
    if not derivacoes_por_grupo and not derivacoes_sem_base:
        linhas.append("- Nenhum.")
        return

    indice_saida = 1

    for indice_grupo in sorted(derivacoes_por_grupo):
        arquivos = ordenar_caminhos(derivacoes_por_grupo[indice_grupo])

        if not arquivos:
            continue

        linhas.append(f"Grupo {indice_saida}:")
        linhas.append(f"Base: Grupo {indice_grupo} de IGUAIS")
        linhas.append("Derivação simples:")

        for arquivo in arquivos:
            linhas.append(f"- {Path(arquivo).name}")

        indice_saida += 1

    if derivacoes_sem_base:
        linhas.append(f"Grupo {indice_saida}:")
        linhas.append("Derivação simples sem grupo-base identificado:")

        for arquivo in ordenar_caminhos(derivacoes_sem_base):
            linhas.append(f"- {Path(arquivo).name}")


def escrever_resumo_diferentes(linhas, resumo_diferentes):
    if not resumo_diferentes:
        linhas.append("- Nenhum.")
        return

    for indice, item in enumerate(resumo_diferentes, start=1):
        linhas.append(f"Grupo {indice}:")
        linhas.append(f"- {Path(item['arquivo']).name}")

        if item["difere_de"]:
            linhas.append(f"  Difere de: {'; '.join(item['difere_de'])}")


# ============================================================
# Montagem do relatório
# ============================================================

def montar_linha_separadora():
    return "-" * 78


def montar_relatorio_comparacao(
    registros,
    resultados_pares,
    arquivos_sem_json,
    grupos_iguais,
    derivacoes_por_grupo,
    derivacoes_sem_base,
):
    linhas = []

    linhas.append("RELATÓRIO DE COMPARAÇÃO DE ESTRUTURAS DE ATOMS/BOXES")
    linhas.append("")

    linhas.append("ARQUIVOS ANALISADOS")
    linhas.append(montar_linha_separadora())

    for indice, registro in enumerate(registros, start=1):
        linhas.append(f"{indice}. {Path(registro['png']).name}")

    linhas.append("")
    linhas.append("RESUMO POR CLASSIFICAÇÃO")
    linhas.append(montar_linha_separadora())

    por_classe = defaultdict(list)

    for resultado in resultados_pares:
        por_classe[resultado["classe"]].append(resultado)

    grupos_exatamente_iguais = agrupar_registros_por_assinatura(
        registros,
        assinatura_exata_nos,
    )

    resumo_diferentes = montar_resumo_diferentes(
        resultados_pares,
        grupos_iguais,
        derivacoes_por_grupo,
        derivacoes_sem_base,
    )

    linhas.append("")
    linhas.append(
        f"EXATAMENTE IGUAIS: "
        f"{len(por_classe.get('EXATAMENTE IGUAIS', []))} par(es)"
    )
    escrever_grupos_de_registros(linhas, grupos_exatamente_iguais)

    linhas.append("")
    linhas.append(
        f"IGUAIS: "
        f"{len(por_classe.get('IGUAIS', []))} par(es)"
    )
    escrever_grupos_de_registros(linhas, grupos_iguais)

    linhas.append("")
    linhas.append(
        f"DERIVAÇÃO SIMPLES: "
        f"{len(por_classe.get('DERIVAÇÃO SIMPLES', []))} par(es)"
    )
    escrever_resumo_derivacoes(
        linhas,
        derivacoes_por_grupo,
        derivacoes_sem_base,
    )

    linhas.append("")
    linhas.append(
        f"DIFERENTES: "
        f"{len(por_classe.get('DIFERENTES', []))} par(es)"
    )
    escrever_resumo_diferentes(linhas, resumo_diferentes)

    linhas.append("")
    linhas.append("COMPARAÇÃO PAR A PAR")
    linhas.append(montar_linha_separadora())

    for item in resultados_pares:
        linhas.append("")
        linhas.append(f"{Path(item['png_a']).name}")
        linhas.append(f"{Path(item['png_b']).name}")
        linhas.append(f"Classificação: {item['classe']}")
        linhas.append(f"Similaridade estrutural: {item['similaridade']:.1%}")
        linhas.append(f"Detalhe: {item['detalhe']}")

    return "\n".join(linhas)


def obter_grupos_iguais(registros):
    grupos_iguais = []

    grupos_por_forma = agrupar_registros_por_assinatura(
        registros,
        assinatura_forma_nos,
    )

    for grupo in grupos_por_forma:
        assinaturas_exatas = {
            assinatura_exata_nos(obter_tree(registro["estrutura"]))
            for registro in grupo
        }

        if len(assinaturas_exatas) >= 2:
            grupos_iguais.append(grupo)

    return grupos_iguais


def gerar_relatorio(registros, arquivos_sem_json, pasta_saida):
    resultados_pares = []

    for registro_a, registro_b in combinations(registros, 2):
        resultado = classificar_par(
            registro_a["estrutura"],
            registro_b["estrutura"],
        )

        resultados_pares.append({
            "png_a": registro_a["png"],
            "png_b": registro_b["png"],
            "classe": resultado["classe"],
            "similaridade": resultado["similaridade"],
            "detalhe": resultado["detalhe"],
        })

    grupos_iguais = obter_grupos_iguais(registros)

    derivacoes_por_grupo, derivacoes_sem_base = montar_resumo_derivacoes(
        resultados_pares,
        grupos_iguais,
    )

    texto_relatorio = montar_relatorio_comparacao(
        registros,
        resultados_pares,
        arquivos_sem_json,
        grupos_iguais,
        derivacoes_por_grupo,
        derivacoes_sem_base,
    )

    caminho_saida = os.path.join(
        pasta_saida,
        "relatorio_comparacao_atoms.txt",
    )

    caminho_tmp = os.path.join(
        os.getenv("TEMP"),
        Path(caminho_saida).name + ".tmp",
    )

    with open(caminho_tmp, "w", encoding="utf-8") as f:
        f.write(texto_relatorio)

    return replace_com_incremento(caminho_tmp, caminho_saida)


# ============================================================
# Entrada PeriTASK
# ============================================================

def executar(arquivos, controls, pasta_saida):
    """
    Entrada padrão do PeriTASK:
    executar(arquivos, controls, pasta_saida)
    """

    arquivos_imagem_png = selecionar_arquivos(arquivos, "imagem_png")

    if not arquivos_imagem_png:
        print(
            "STATUS:Nenhum arquivo PNG encontrado para comparação.",
            flush=True,
        )
        return

    registros = []
    arquivos_sem_json = []

    total = len(arquivos_imagem_png)

    for i, arquivo in enumerate(arquivos_imagem_png, start=1):
        try:
            estrutura = extrair_estrutura_json_do_png(arquivo)

            if not estrutura:
                arquivos_sem_json.append(arquivo)
            elif estrutura.get("schema") != PNG_SCHEMA:
                arquivos_sem_json.append(arquivo)
            else:
                registros.append({
                    "png": arquivo,
                    "estrutura": estrutura,
                })

        except Exception:
            arquivos_sem_json.append(arquivo)

        progresso = int(i / total * 50)
        print(f"PROGRESS:{progresso}", flush=True)

    if len(registros) < 2:
        print(
            "STATUS:São necessários pelo menos dois PNGs válidos com estrutura "
            "JSON embutida para comparação.",
            flush=True,
        )
        return

    caminho_relatorio = gerar_relatorio(
        registros,
        arquivos_sem_json,
        pasta_saida,
    )

    print("PROGRESS:100", flush=True)