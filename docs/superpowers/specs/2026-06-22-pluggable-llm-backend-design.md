# Design: Backend de LLM plugável (LiteLLM) + README open source

**Data:** 2026-06-22
**Status:** Aprovado para planejamento

## Objetivo

Permitir que o news-intelligence-assistant ("Bem-te-vi") use qualquer provedor de LLM — Anthropic na nuvem (default, comportamento atual) ou um modelo **local** (Ollama e afins via API OpenAI-compatível) — escolhido por configuração, sem mudar código. E criar um `README.md` estilo projeto open source que documente o setup completo, incluindo as opções de modelo e os tiers de hardware.

Motivação: o projeto será publicado como **open source** para outras pessoas rodarem em hardware variado (ver restrição abaixo). Forçar Anthropic excluiria quem não tem chave de API ou quer rodar de graça/local.

## Restrições de arquitetura

- **Stateless:** nenhuma persistência entre execuções (requisito do GitHub Actions). Esta feature não introduz estado — só troca de onde a inferência acontece.
- **Open source / hardware variado:** defaults devem ser acessíveis; o usuário escolhe um modelo do tamanho do seu hardware via config. Não hardcodar modelo pesado.
- **Python 3.11+**, todos os testes com `pytest` mockando chamadas externas.

---

## Componente 1: `src/llm.py` (abstração via LiteLLM)

Wrapper fino sobre `litellm.completion`, com uma função única usada pelo analyzer e pelo deduplicator:

```python
import os
import litellm

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def complete(system: str, user: str, max_tokens: int = 4096) -> str:
    kwargs = {
        "model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    api_base = os.getenv("LLM_API_BASE")
    if api_base:
        kwargs["api_base"] = api_base
    api_key = os.getenv("LLM_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key
    response = litellm.completion(**kwargs)
    return response.choices[0].message.content
```

### Configuração (variáveis de ambiente)

| Env | Default | Usada para |
|---|---|---|
| `LLM_MODEL` | `claude-haiku-4-5-20251001` | string do modelo no formato LiteLLM (o provedor está embutido, ex: `ollama/qwen2.5:7b`) |
| `LLM_API_BASE` | — (não enviado) | endpoint de provedores locais/custom (ex: `http://localhost:11434`) |
| `LLM_API_KEY` | — (não enviado) | provedores que exigem chave não-padrão (ex: OpenRouter) |
| `ANTHROPIC_API_KEY` | — (existente) | lida automaticamente pelo LiteLLM quando o modelo é Anthropic |

### Decisões de design

- **Sem `LLM_BACKEND`:** no LiteLLM o provedor está embutido na string do modelo, então `LLM_MODEL` já é o seletor. O default Anthropic preserva o comportamento do GitHub Actions.
- **Sem prompt caching explícito:** o caminho unificado abre mão do `cache_control: ephemeral` (que era só-Anthropic). Impacto de custo desprezível (system prompt pequeno, poucos batches/dia); inexistente nos modelos locais.
- **`api_base`/`api_key` só são enviados quando setados** — evita sobrescrever a resolução padrão do LiteLLM no caminho Anthropic.
- **Parsing tolerante mantido:** os callers continuam extraindo o `[...]` mesmo com texto em volta (modelos locais são menos disciplinados que o Haiku).

---

## Componente 2: Migração dos callers

Sem mudança de comportamento observável — só trocam o SDK Anthropic direto por `complete(...)`.

### `src/analyzer.py`
- Remove `import anthropic` e `import os` (o `os.getenv` da API key sai daqui).
- Adiciona `from src.llm import complete`.
- Dentro de `analyze`, o bloco `client = anthropic.Anthropic(...)` + `client.messages.create(...)` vira:
  ```python
  text = complete(SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False), max_tokens=4096)
  results = _parse_response(text, batch)
  all_results.extend(results)
  ```
- Mantém `SYSTEM_PROMPT`, `_build_batches`, `_parse_response` e o `try/except` por batch (agora pega exceções do LiteLLM).

### `src/deduplicator.py`
- Remove `import anthropic` e `import os`.
- Adiciona `from src.llm import complete`.
- O bloco do cliente Anthropic vira:
  ```python
  text = complete(DEDUP_PROMPT, json.dumps(payload, ensure_ascii=False), max_tokens=2048)
  groups = _parse_groups(text, len(articles))
  ```
- Mantém `DEDUP_PROMPT`, `_no_dedup`, `_parse_groups` e o `try/except` que cai no fallback no-dedup + `status.add(...)` (agora também em erro do LiteLLM).

---

## Componente 3: Dependências

`requirements.txt`:
- **Adiciona** `litellm==<versão exata resolvida na implementação>`. A versão DEVE ser pinada (igualdade exata), não `>=`. Comentário no arquivo: `# pinned; review on upgrade (litellm releases frequently)`.
- **Remove** `anthropic>=0.40.0` — nenhum código importa `anthropic` direto após a migração; o LiteLLM cobre o provedor Anthropic.

---

## Componente 4: README open source ("Bem-te-vi")

Novo `README.md` na raiz (hoje inexistente). Tom acolhedor, emojis nos cabeçalhos, exemplos copiáveis, o passarinho como mascote. Nome do programa: **Bem-te-vi** (passarinho brasileiro; o nome quer dizer "bem te vi" — o programa "vê as notícias por você").

Seções:
1. **Título + tagline** — `# 🐦 Bem-te-vi` + uma linha do que faz.
2. **Badges** — Python 3.11+, License MIT, tests.
3. **✨ Funcionalidades** — Gmail + RSS, análise com IA, dedup semântica, relatório no Telegram, roda de graça no GitHub Actions, IA na nuvem OU local.
4. **🔍 Como funciona** — diagrama: coleta → dedup → análise → Telegram.
5. **📸 Exemplo** — amostra do relatório do Telegram.
6. **🚀 Início rápido** — clone → `.env` → `python main.py`.
7. **⚙️ Configuração (`.env`)** — tabela de todas as envs, incluindo `LLM_*`.
8. **🧠 Escolha do modelo** — trilha Nuvem (Anthropic) vs Local (Ollama: instalar → `ollama pull qwen2.5:7b` → setar `LLM_MODEL`/`LLM_API_BASE`).
9. **💻 Hardware** — a tabela de tiers (abaixo).
10. **📧 Setup do Gmail** — Google Cloud (Gmail API, OAuth Desktop, test user) + `setup_gmail_auth.py`.
11. **💬 Setup do Telegram** — BotFather (token) + como obter o chat id.
12. **🤖 GitHub Actions** — secrets (`ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GMAIL_TOKEN_JSON`) + agendamento.
13. **🤝 Contribuindo · 📄 Licença (MIT).**

### Tabela de hardware (conteúdo exato)

| Hardware | `LLM_MODEL` | `LLM_API_BASE` | Nota |
|---|---|---|---|
| Nuvem (qualquer máquina) | `claude-haiku-4-5-20251001` *(default)* | — | precisa `ANTHROPIC_API_KEY` |
| CPU apenas | `ollama/qwen2.5:3b` | `http://localhost:11434` | funciona, lento |
| GPU 6–8 GB | `ollama/qwen2.5:7b` | `http://localhost:11434` | recomendado p/ maioria |
| GPU 12–16 GB | `ollama/qwen2.5:14b` | `http://localhost:11434` | melhor qualidade |
| GPU 24 GB+ | `ollama/qwen2.5:32b` | `http://localhost:11434` | mais perto do Haiku |

### `.env.example`
Adicionar as `LLM_*` comentadas com exemplos (mantendo as existentes):
```
# LLM (default: Anthropic na nuvem). Para rodar local, veja o README.
# LLM_MODEL=claude-haiku-4-5-20251001
# LLM_API_BASE=http://localhost:11434
# LLM_API_KEY=
```

---

## GitHub Actions

Nenhuma mudança no workflow. Ele já instala `requirements.txt` (agora com LiteLLM) e exporta `ANTHROPIC_API_KEY`, que o LiteLLM lê automaticamente. Default `LLM_MODEL` = Haiku → comportamento idêntico ao atual.

---

## Estratégia de testes

Todos com `pytest`, mockando chamadas externas.

### `src/llm.py` — novo `tests/test_llm.py`
- `complete` usa `DEFAULT_MODEL` quando `LLM_MODEL` não está setado (mock `litellm.completion`, inspeciona kwargs).
- `LLM_MODEL` setado é repassado como `model`.
- `api_base` e `api_key` são incluídos nos kwargs apenas quando as envs estão setadas; ausentes quando não.
- Retorna `response.choices[0].message.content`.

### Migração — testes existentes
- `tests/test_analyzer.py`: trocar `patch("anthropic.Anthropic")` por `patch("src.analyzer.complete", return_value="<json string>")`. Remover a montagem de `MagicMock.content[0].text`. Asserções sobre resultados permanecem.
- `tests/test_deduplicator.py`: trocar `patch("anthropic.Anthropic")` por `patch("src.deduplicator.complete", return_value="<json string>")`. Asserções permanecem (agrupamento, representante, fallback, fontes).
- Os testes de fallback continuam válidos: `complete` lançando exceção → analyzer ignora o batch / deduplicator cai no no-dedup + aviso.

---

## Fora de escopo (YAGNI)

- LangChain / LangGraph (overkill para pipeline linear/stateless; só fariam sentido se o projeto virar agêntico — features de follow-up interativo e feedback).
- Re-adicionar prompt caching de forma provider-específica.
- Modelos/endpoints por-caller separados (analyzer vs dedup usam o mesmo `LLM_MODEL`).
- Auto-detecção de hardware ou download automático de modelos.
