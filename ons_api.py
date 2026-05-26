"""
Baixa arquivos do ONS - RESTRICAO COFF (fotovoltaica ou eolica)
"""

import requests
from pathlib import Path
import sys

def main(tipo=None, anos=None, meses=None):
    """
    Baixa arquivos Parquet/CSV do ONS
    
    Args:
        tipo: 'fotovoltaica', 'eolica' ou 'eolica_csv'
        anos: Lista de anos
        meses: Lista de meses
    """
    
    BASE = "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset"

    config = {
        "fotovoltaica": {
            "url": f"{BASE}/restricao_coff_fotovoltaica_tm",
            "pasta": "dados_fotovoltaica",
            "prefixo": "RESTRICAO_COFF_FOTOVOLTAICA",
            "formato": "parquet",
            "ano_inicio": None,
            "ano_fim": None,
            "mes_fim": None,
        },
        "eolica": {
            "url": f"{BASE}/restricao_coff_eolica_tm",
            "pasta": "dados_eolica",
            "prefixo": "RESTRICAO_COFF_EOLICA",
            "formato": "parquet",
            "ano_inicio": 2023,
            "ano_fim": None,
            "mes_fim": None,
        },
        "eolica_csv": {
            "url": f"{BASE}/restricao_coff_eolica_tm",
            "pasta": "dados_eolica",
            "prefixo": "RESTRICAO_COFF_EOLICA",
            "formato": "csv",
            "ano_inicio": 2021,
            "ano_fim": 2023,
            "mes_fim": 9,  # setembro de 2023 é o último
        },
    }

    # Menu interativo
    if tipo is None:
        print("\nQual tipo de dado?")
        print("  1 - Fotovoltaica            (Parquet | sem limite)")
        print("  2 - Eólica                  (Parquet | out/2023 em diante)")
        print("  3 - Eólica CSV              (CSV     | jan/2021 a set/2023)")
        opcao = input("Escolha (1, 2 ou 3): ")

        if opcao == "1":
            tipo = "fotovoltaica"
        elif opcao == "2":
            tipo = "eolica"
        elif opcao == "3":
            tipo = "eolica_csv"
        else:
            print("Opção inválida")
            return

    tipo = tipo.lower()
    if tipo not in config:
        print(f"Tipo deve ser: fotovoltaica, eolica ou eolica_csv")
        print(f"Uso: python ons_api.py --tipo eolica_csv --anos 2021-2023 --meses 1-12")
        return

    cfg = config[tipo]
    pasta = Path(cfg["pasta"])
    pasta.mkdir(exist_ok=True)

    S3_URL  = cfg["url"]
    PREFIXO = cfg["prefixo"]
    FORMATO = cfg["formato"]

    meses_nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março",    4: "Abril",
        5: "Maio",    6: "Junho",     7: "Julho",     8: "Agosto",
        9: "Setembro",10: "Outubro",  11: "Novembro", 12: "Dezembro"
    }

    # ── Anos ──────────────────────────────────────────────────────────────
    if anos is None:
        ano_inicio_hint = cfg["ano_inicio"] or 2021
        ano_fim_hint    = cfg["ano_fim"]    or 2025

        if cfg["ano_inicio"] and cfg["ano_fim"]:
            hint = f"{cfg['ano_inicio']}-{cfg['ano_fim']}"
        elif cfg["ano_inicio"]:
            hint = f"{cfg['ano_inicio']} em diante"
        else:
            hint = "ex: 2024 ou 2023,2024 ou 2023-2025"

        try:
            entrada_ano = input(f"\nQual(is) ano(s)? ({hint}): ")
            if "-" in entrada_ano:
                inicio, fim = entrada_ano.split("-")
                anos = list(range(int(inicio.strip()), int(fim.strip()) + 1))
            elif "," in entrada_ano:
                anos = [int(a.strip()) for a in entrada_ano.split(",")]
            else:
                anos = [int(entrada_ano.strip())]
        except ValueError:
            print("Ano inválido")
            return

    # Validar limites do tipo
    if cfg["ano_inicio"]:
        anos_invalidos = [a for a in anos if a < cfg["ano_inicio"]]
        if anos_invalidos:
            print(f"⚠ Atenção: anos {anos_invalidos} são anteriores ao início do período ({cfg['ano_inicio']}), serão ignorados")
            anos = [a for a in anos if a >= cfg["ano_inicio"]]

    if cfg["ano_fim"]:
        anos_invalidos = [a for a in anos if a > cfg["ano_fim"]]
        if anos_invalidos:
            print(f"⚠ Atenção: anos {anos_invalidos} são posteriores ao fim do período ({cfg['ano_fim']}), serão ignorados")
            anos = [a for a in anos if a <= cfg["ano_fim"]]

    if not anos:
        print("Nenhum ano válido para este tipo")
        return

    # ── Meses ─────────────────────────────────────────────────────────────
    if meses is None:
        print("\nQuais meses?")
        print("Opções: 1,2,3 ou 1-12")
        entrada = input("Meses: ")

        if "-" in entrada:
            partes = entrada.split("-")
            meses = list(range(int(partes[0].strip()), int(partes[1].strip()) + 1))
        else:
            meses = [int(m.strip()) for m in entrada.split(",")]

    meses = sorted(set([m for m in meses if 1 <= m <= 12]))

    if not meses:
        print("Nenhum mês válido")
        return

    total_arquivos = len(anos) * len(meses)

    # ── Download ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"Baixando até {total_arquivos} arquivo(s)")
    print(f"  Tipo   : {tipo.upper()}")
    print(f"  Formato: {FORMATO.upper()}")
    print(f"  Anos   : {anos[0]} a {anos[-1]} ({len(anos)} ano(s))")
    print(f"  Meses  : {len(meses)}")
    print("=" * 70)

    arquivos_ok   = 0
    erros         = 0
    pulados       = 0
    total_tamanho = 0
    contador      = 0

    for ano_atual in anos:
        pasta_ano = pasta / str(ano_atual)
        pasta_ano.mkdir(exist_ok=True)

        print(f"\n── {ano_atual} ──")

        for mes in meses:
            contador += 1

            # Corte eolica_csv: máximo set/2023
            if cfg["ano_fim"] and cfg["mes_fim"]:
                if ano_atual == cfg["ano_fim"] and mes > cfg["mes_fim"]:
                    print(f"[{contador}/{total_arquivos}] {meses_nomes[mes]:10s} ({ano_atual}-{mes:02d})... ⚠ fora do período ({FORMATO.upper()} vai até {meses_nomes[cfg['mes_fim']]}/{cfg['ano_fim']}), pulando")
                    pulados += 1
                    continue

            filename = f"{PREFIXO}_{ano_atual}_{mes:02d}.{FORMATO}"
            url      = f"{S3_URL}/{filename}"
            filepath = pasta_ano / filename

            try:
                print(f"[{contador}/{total_arquivos}] {meses_nomes[mes]:10s} ({ano_atual}-{mes:02d})...", end=" ", flush=True)

                response = requests.get(url, timeout=60)
                response.raise_for_status()

                filepath.write_bytes(response.content)

                tamanho_mb     = filepath.stat().st_size / (1024 * 1024)
                total_tamanho += tamanho_mb
                arquivos_ok   += 1

                print(f"✓ ({tamanho_mb:.1f} MB)")

            except Exception as e:
                erros += 1
                print(f"✗ {e}")

    # ── Resumo ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"Resumo:")
    print(f"  Tipo   : {tipo.upper()}")
    print(f"  Formato: {FORMATO.upper()}")
    print(f"  Anos   : {anos[0]} a {anos[-1]}")
    print(f"  Sucesso: {arquivos_ok}/{total_arquivos}")
    print(f"  Pulados: {pulados}")
    print(f"  Erros  : {erros}")
    print(f"  Total  : {total_tamanho:.1f} MB")
    print(f"  Pasta  : {pasta.absolute()}")
    print("=" * 70)

    if arquivos_ok > 0:
        print(f"\nPróximos passos:")
        print(f"  import pandas as pd")
        if FORMATO == "parquet":
            print(f"  df = pd.read_parquet('{pasta}/')")
        else:
            print(f"  df = pd.concat([pd.read_csv(f) for f in Path('{pasta}').rglob('*.csv')])")


if __name__ == "__main__":
    tipo  = None
    anos  = None
    meses = None

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]

        if arg == "--tipo" and i + 1 < len(sys.argv):
            tipo = sys.argv[i + 1].lower()
            i += 2
        elif arg == "--anos" and i + 1 < len(sys.argv):
            anos_str = sys.argv[i + 1]
            if "-" in anos_str:
                inicio, fim = anos_str.split("-")
                anos = list(range(int(inicio.strip()), int(fim.strip()) + 1))
            elif "," in anos_str:
                anos = [int(a.strip()) for a in anos_str.split(",")]
            else:
                anos = [int(anos_str.strip())]
            i += 2
        elif arg == "--meses" and i + 1 < len(sys.argv):
            meses_str = sys.argv[i + 1]
            if "-" in meses_str:
                inicio, fim = meses_str.split("-")
                meses = list(range(int(inicio), int(fim) + 1))
            else:
                meses = [int(m.strip()) for m in meses_str.split(",")]
            i += 2
        else:
            i += 1

    main(tipo=tipo, anos=anos, meses=meses)