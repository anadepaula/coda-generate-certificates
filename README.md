# Gerador de certificados

O código está dividido em `attendance.py` (leitura dos CSVs, elegibilidade e relatórios), `certificate_pdf.py` (formatação e geração dos PDFs) e `generator.py` (CLI e coordenação).

O gerador lê `inputs/atividades.csv` e `inputs/checkins.csv` por padrão. As atividades são relacionadas aos check-ins pelo campo `atividades.id` = `checkins.codigo`.

O CSV de atividades usa `id`, `slug`, `atividade`, `hora_inicio` e `hora_termino`; a data é obtida dos primeiros oito dígitos da slug. O CSV de check-ins usa `codigo`, `nome`, `email`, `check_in` e `assinado`.

A pessoa recebe certificado se `check_in` **ou** `assinado` for `TRUE`. O gerador cria `certificados.csv` e `sem_certificado.csv` em `generated-certificates/`, junto com um PDF por pessoa elegível e `certificates-all.pdf`. `certificados.csv` inclui o motivo da elegibilidade e o nome do PDF individual; `sem_certificado.csv` não inclui justificativa. Cada nome de arquivo preserva a slug da atividade e acrescenta o nome da pessoa em minúsculas, transliterado para ASCII, com palavras separadas por `_`.

Para informar outros arquivos:

```bash
uv run fill-pdf-form \
  --activities-csv atividades.csv \
  --attendees-csv checkins.csv
```

O template padrão é `template.pdf`; use `--template` e `--output-dir` para substituir o template e o diretório de saída.

## Arquivos de exemplo

`examples/atividades.csv` e `examples/checkins.csv` contêm apenas registros fictícios e usam e-mails reservados em `.invalid`. Para testar o fluxo sem misturar os resultados aos certificados reais:

```bash
uv run fill-pdf-form \
  --activities-csv examples/atividades.csv \
  --attendees-csv examples/checkins.csv \
  --output-dir generated-certificates/exemplos
```
