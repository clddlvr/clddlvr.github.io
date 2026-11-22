"""Gera painel_v11/dados.js a partir de dados.xlsx.

Executar a partir da pasta do projeto:
    python3 painel_v11/gera_dados_v11.py

Parte dos mesmos dados das versões 7 a 10 (painel_v7/gera_dados_v7.py): áreas de
avaliação com o nome de 2025 e programa de fomento como dimensão. A diferença é a
recuperação da área de avaliação em 2017, 2018 e 2019, anos em que a base traz
todas as bolsas como "INDEFINIDA" (sem área), mas mantém o código do programa
de pós-graduação. A área é atribuída pelo código do programa, com estas regras:

1. Programa com uma única área de avaliação nos demais anos da base (já com os
   nomes de 2025): recebe essa área.
2. Programa que teve mais de uma área ao longo do tempo: recebe a área que tinha
   em 2020 (se em 2020 tiver mais de uma, a que reúne mais bolsas).
3. Programa com mais de uma área e ausente em 2020: recebe a área do ano mais
   próximo de 2020 em que aparece (empate: o ano posterior).
4. Bolsa sem código de programa, ou programa sem área conhecida em nenhum outro
   ano: continua "INDEFINIDA (sem área de avaliação)".

Só os anos 2017 a 2019 são tratados; nos demais anos, as bolsas sem área ficam
como estão na base. As contagens de cada regra vão para DADOS.imputacao, que o
painel mostra no rodapé.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "painel"))
sys.path.insert(0, str(RAIZ / "painel_v7"))
from gera_dados_painel import ENTRADA, MODALIDADES, REGIOES, linhas_xlsx  # noqa: E402
from gera_dados_v7 import AREA_2025  # noqa: E402

SAIDA = Path("painel_v11/dados.js")
ANOS_SEM_AREA = {2017, 2018, 2019}
ANO_REF = 2020
INDEF = "INDEFINIDA (sem área de avaliação)"


def bolsas_da_linha(r, pos):
    return {col: int(float(r[pos[col]])) for col in MODALIDADES if r[pos[col]] not in ("", "0", "0.0")}


def main():
    linhas = linhas_xlsx(ENTRADA)
    cab = next(linhas)
    pos = {nome: i for i, nome in enumerate(cab)}
    for col in ["Ano", "UF", "Região", "IES", "Área Avaliação", "Programa Fomento", "Código Programa", *MODALIDADES]:
        if col not in pos:
            sys.exit(f"Coluna ausente na base: {col}")

    brutos = list(linhas)
    n_linhas = len(brutos)

    # Programa de fomento: une grafias que só diferem em maiúsculas/minúsculas
    nome_prog = lambda r: " ".join(r[pos["Programa Fomento"]].split()) or "(não informado)"  # noqa: E731
    grafias = Counter(nome_prog(r) for r in brutos)
    melhor = {}
    for g, _ in grafias.most_common():
        melhor.setdefault(g.upper(), g)
    unidos = sorted({g for g in grafias if melhor[g.upper()] != g})

    def area_base(r):
        a = r[pos["Área Avaliação"]].strip()
        return INDEF if a in ("", "INDEFINIDA") else AREA_2025.get(a, a)

    # Referência: área de cada código de programa, por ano, fora de 2017-2019
    ref = defaultdict(lambda: defaultdict(Counter))  # código -> ano -> área -> bolsas
    for r in brutos:
        ano = int(float(r[pos["Ano"]]))
        cod = r[pos["Código Programa"]].strip()
        area = area_base(r)
        if ano in ANOS_SEM_AREA or not cod or area == INDEF:
            continue
        ref[cod][ano][area] += sum(bolsas_da_linha(r, pos).values()) or 1

    def imputar(cod):
        """Devolve (área, regra) para um código de programa de 2017-2019."""
        if not cod:
            return INDEF, "sem_codigo"
        anos = ref.get(cod)
        if not anos:
            return INDEF, "sem_area_conhecida"
        areas = set().union(*(set(c) for c in anos.values()))
        if len(areas) == 1:
            return next(iter(areas)), "area_unica"
        if ANO_REF in anos:
            return anos[ANO_REF].most_common(1)[0][0], "area_2020"
        ano = min(anos, key=lambda a: (abs(a - ANO_REF), -a))
        return anos[ano].most_common(1)[0][0], "ano_mais_proximo"

    soma = defaultdict(int)
    uf_regiao = {}
    regras = Counter()          # bolsas por regra
    regras_ano = defaultdict(Counter)
    for r in brutos:
        ano = int(float(r[pos["Ano"]]))
        uf = r[pos["UF"]]
        uf_regiao[uf] = REGIOES.get(r[pos["Região"]], r[pos["Região"]])
        ies = r[pos["IES"]] or "(IES não informada)"
        area = area_base(r)
        b = bolsas_da_linha(r, pos)
        if ano in ANOS_SEM_AREA and area == INDEF:
            area, regra = imputar(r[pos["Código Programa"]].strip())
            regras[regra] += sum(b.values())
            regras_ano[ano][regra] += sum(b.values())
        prog = melhor[nome_prog(r).upper()]
        for col, n in b.items():
            soma[(ano, uf, ies, area, col, prog)] += n

    ufs = sorted({k[1] for k in soma})
    ies = sorted({k[2] for k in soma})
    areas = sorted({k[3] for k in soma})
    mods = list(MODALIDADES)
    progs = sorted({k[5] for k in soma})
    idx = lambda vals: {v: i for i, v in enumerate(vals)}  # noqa: E731
    i_uf, i_ies, i_area, i_mod, i_prog = idx(ufs), idx(ies), idx(areas), idx(mods), idx(progs)
    rows = [[a, i_uf[u], i_ies[s], i_area[ar], i_mod[m], i_prog[p], n]
            for (a, u, s, ar, m, p), n in sorted(soma.items())]

    total_imp = sum(regras.values())
    saida = {
        "dims": {
            "uf": ufs,
            "regiao": [uf_regiao[u] for u in ufs],
            "ies": ies,
            "area": areas,
            "modalidade": [MODALIDADES[m][0] for m in mods],
            "nivel": [MODALIDADES[m][1] for m in mods],
            "programa": progs,
        },
        "columns": ["ano", "uf", "ies", "area", "modalidade", "programa", "bolsas"],
        "rows": rows,
        "fonte": "dados.xlsx (CAPES/DPB), " + f"{n_linhas:,}".replace(",", ".") + " linhas",
        "areas_renomeadas": AREA_2025,
        "programas_unidos": {g: melhor[g.upper()] for g in unidos},
        "imputacao": {
            "anos": sorted(ANOS_SEM_AREA),
            "bolsas": total_imp,
            "area_unica": regras["area_unica"],
            "area_2020": regras["area_2020"],
            "ano_mais_proximo": regras["ano_mais_proximo"],
            "sem_codigo": regras["sem_codigo"],
            "sem_area_conhecida": regras["sem_area_conhecida"],
            "por_ano": {str(a): dict(c) for a, c in sorted(regras_ano.items())},
        },
    }
    SAIDA.write_text("// Gerado por painel_v11/gera_dados_v11.py — não editar à mão\n"
                     "window.DADOS = " + json.dumps(saida, ensure_ascii=False, separators=(",", ":")) + ";\n",
                     encoding="utf-8")

    print(f"{n_linhas} linhas lidas -> {len(rows)} combinações; {sum(r[6] for r in rows)} bolsas; {len(areas)} áreas")
    pct = lambda n: f"{n:>7} ({100 * n / total_imp:5.1f}%)"  # noqa: E731
    print(f"2017-2019: {total_imp} bolsas sem área na base")
    for k in ["area_unica", "area_2020", "ano_mais_proximo", "sem_codigo", "sem_area_conhecida"]:
        print(f"  {k:20s} {pct(regras[k])}")
    print(f"  {SAIDA} ({SAIDA.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
