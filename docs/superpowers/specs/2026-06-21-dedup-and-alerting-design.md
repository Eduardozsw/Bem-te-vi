# Design: Deduplicação semântica + Alertas de saúde da execução

**Data:** 2026-06-21
**Status:** Aprovado para planejamento

## Objetivo

Adicionar duas features ao news-intelligence-assistant, ambas dentro da arquitetura **stateless** atual (nada persiste entre execuções — requisito para rodar no GitHub Actions sem infra extra):

1. **Deduplicação semântica** — agrupar notícias que cobrem o mesmo fato, vindas de fontes diferentes, num único item do relatório.
2. **Alertas de saúde da execução** — avisar o usuário (via Telegram e/ou exit code) quando o pipeline quebra, uma fonte falha, a execução vem vazia, ou a entrega ao Telegram falha.

## Restrição de arquitetura

O pipeline **deve permanecer stateless**. Os runners do GitHub Actions são efêmeros (VM nova a cada run, disco apagado ao fim do job); statelessness é o que permite rodar lá sem persistência externa. Ambas as features operam **dentro de um único run** — chamadas de API extras e processamento em memória apenas, sem gravar estado entre execuções.

---

## Feature 1: Deduplicação semântica

### Fluxo

```
coleta (gmail + rss) → [dedup] → análise em lotes de 10 → relatório
```

A dedup é um passo novo entre a coleta e a análise.

### Componente: `src/deduplicator.py`

```python
def deduplicate(articles: list[Article]) -> list[Article]:
    ...
```

- Faz **uma** chamada ao Claude Haiku passando apenas `{índice, título, fonte}` de cada artigo (sem o corpo → barato).
- O modelo devolve grupos de índices que tratam do mesmo fato, ex: `[[0, 3], [1], [2, 4]]`.
- Para cada grupo:
  - Escolhe o **representante** = artigo com maior `len(content)`.
  - Define `representante.sources` = lista ordenada e sem repetição de todas as fontes do grupo.
- Retorna a lista de representantes.

**Degradação graciosa:** se a chamada ao Haiku falhar (exceção ou JSON inválido), cada artigo vira seu próprio grupo de um item — o pipeline segue sem dedup, nada quebra. O erro é logado e registrado como aviso (ver Feature 2).

### Mudanças nos modelos (`src/models.py`)

```python
@dataclass
class Article:
    source: str
    title: str
    content: str
    url: str
    published_at: datetime
    sources: list[str] = field(default_factory=list)   # NOVO

@dataclass
class AnalysisResult:
    title: str
    source: str
    url: str
    relevance: int
    summary: str
    why_it_matters: str
    impacts: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)   # NOVO
```

- `Article.sources`: preenchido pelo `deduplicate` no representante. Para artigos não-deduplicados (ou quando dedup falha), default `[]` e o consumidor usa `[source]` como fallback.
- `AnalysisResult.sources`: o analyzer copia de `article.sources` (fallback `[article.source]` se vazio).

### Mudança no analyzer (`src/analyzer.py`)

- Ao construir cada `AnalysisResult`, define `sources = article.sources or [article.source]`.
- Nenhuma mudança no batching nem no prompt de análise (a dedup já aconteceu antes).

### Mudança no relatório (`src/telegram_sender.py`)

- Em `format_report`, na linha de fonte de cada item importante:
  - Se `len(result.sources) > 1`: `📌 Visto em: A, B, C`.
  - Caso contrário: `📌 Fonte: X` (comportamento atual).
- Quanto mais fontes cobrem a mesma notícia, mais forte o sinal de relevância para o leitor.

### Mudança no pipeline (`main.py`)

- Chama `deduplicate(all_articles)` entre a coleta e `analyze(...)`.
- `total_analyzed` passa a refletir o número de itens **após** dedup (notícias distintas), não o bruto coletado.

---

## Feature 2: Alertas de saúde da execução

Entrega no modelo **A** (aprovado): status embutido no próprio relatório quando há relatório; mensagem dedicada apenas quando não há relatório (crash); exit code para acionar o email do GitHub Actions.

### Componente: `RunStatus`

Dataclass simples (em `src/run_status.py`), criada no `main()` e passada adiante. Vive só em memória durante o run.

```python
@dataclass
class RunStatus:
    warnings: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.warnings.append(message)
```

### Coleta de avisos nos readers

Assinaturas ganham parâmetro opcional `status` (retrocompatível — tipo de retorno continua `list[Article]`):

```python
def read_gmail(label: str = "newsletters", status: "RunStatus | None" = None) -> list[Article]: ...
def read_rss_feeds(config_path: str = "config.yaml", status: "RunStatus | None" = None) -> list[Article]: ...
```

- Em falha parcial, o reader chama `status.add(...)` em vez de só logar e sumir:
  - Gmail label não encontrada → `status.add("Gmail: label 'newsletters' não encontrada")`
  - Falha de autenticação Gmail → `status.add("Gmail: falha de autenticação")`
  - Feed RSS fora do ar → `status.add("RSS 'TechCrunch' fora do ar")`
- Quando `status is None`, o comportamento atual (só log) é mantido.

### Mapeamento dos 4 gatilhos

| Gatilho | Tratamento |
|---|---|
| Fonte falhou parcialmente | Aviso no `RunStatus` → **rodapé** do relatório diário |
| Execução vazia (0 artigos) | Relatório enviado mesmo assim ("rodei, 0 conteúdos") + rodapé — confirmação positiva |
| Pipeline quebrou (crash) | `main()` envolve o pipeline em try/except → `send_alert("🚨 Pipeline falhou: <erro>")` + `exit(1)` |
| Falha no envio do Telegram | `send_report` retorna `bool`; se não entregou → log + `exit(1)` (Telegram fora → aviso vai pelo email do Actions) |

### Mudanças em `src/telegram_sender.py`

- `format_report(results, total_analyzed, warnings: list[str] | None = None)`:
  - Se `warnings` não vazio, acrescenta seção final `⚠️ *Avisos*` com um item por aviso.
- `send_report(...) -> bool`: retorna `True` se ao menos a entrega das mensagens teve sucesso; `False` se todas falharam. Recebe e repassa `warnings` ao `format_report`.
- Nova função `send_alert(text: str) -> bool`: envia uma única mensagem curta de alerta (usada no caso de crash). Reaproveita a mesma lógica de POST do `send_report`.

### Mudanças em `main.py`

- Cria `status = RunStatus()` e passa aos readers.
- Detecta execução vazia (`len(all_articles) == 0`) e registra aviso correspondente; ainda assim chama `send_report` para confirmar que rodou.
- Envolve o pipeline em `try/except`:
  - Em exceção não tratada → `send_alert("🚨 Pipeline falhou: <erro>")`, loga, e `sys.exit(1)`.
- Após `send_report`, se retornou `False` (entrega falhou) → loga e `sys.exit(1)`.
- Em execução de sucesso com entrega ok → exit 0.

O `exit(1)` é o que marca a execução como vermelha no GitHub Actions e dispara o email automático — cobrindo o caso em que o próprio Telegram está indisponível.

---

## Estratégia de testes

Todos os testes com `pytest`, mockando chamadas externas (mesmo padrão do projeto).

### Feature 1
- `deduplicate` agrupa corretamente dado um retorno mockado do Haiku (ex: 5 artigos → 3 grupos).
- Representante escolhido é o de maior `content`.
- `representante.sources` contém todas as fontes do grupo, sem repetição.
- **Degradação:** se o cliente Haiku lança exceção, `deduplicate` retorna 1 artigo por grupo (sem perda).
- Analyzer popula `AnalysisResult.sources` (de `article.sources`, com fallback `[source]`).
- `format_report` mostra `Visto em:` quando >1 fonte e `Fonte:` quando 1.

### Feature 2
- Reader registra aviso no `RunStatus` quando a label não existe / feed falha.
- Reader sem `status` (None) mantém comportamento atual.
- `format_report` inclui seção `⚠️ Avisos` quando há warnings, e omite quando não há.
- `send_report` retorna `False` quando todas as entregas falham, `True` quando sucesso.
- `main()` chama `send_alert` e sai com código ≠0 quando o pipeline lança exceção (mockar um reader pra estourar).
- `main()` envia relatório de execução vazia quando 0 artigos.

---

## Fora de escopo (YAGNI)

- Dedup entre dias / histórico de notícias já vistas (exigiria persistência → quebra stateless).
- Feedback de relevância (👍/👎) e follow-up interativo (features 3 e 4 — exigem estado + interatividade).
- Configuração de severidade/roteamento de alertas além do par Telegram + exit code.
