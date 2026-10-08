# Preparação da entrega da Sprint 2

> **For agentic workers:** Use superpowers:executing-plans para executar as etapas nesta sessão. Escopo aprovado pelo autor em 08/10/2026, após a revisão dos enunciados e do repositório.

**Goal:** organizar as duas sprints no mesmo repositório, tornar a implementação reproduzível e preparar a entrega da Fase 6.

**Architecture:** preservar código, dados e histórico nos caminhos atuais; arquivar a versão publicada da Sprint 1 e apresentar a Sprint 2 no README principal. Corrigir as expectativas desatualizadas dos testes sem mudar o comportamento do produto.

**Tech Stack:** Markdown, TXT, Next.js, FastAPI, Playwright, pytest.

**Spec:** enunciado `fase-6/trabalhos/challenge good-we sprint-2.pdf` no workspace FIAP e aprovação do autor nesta conversa. A fonte será copiada sem alteração para `docs/sprints/sprint-02/enunciado.pdf`.

## Restrições

- Mesmo repositório GitHub: `paulo-faulstich/ev-chargeops`.
- Preservar as 30 alterações/arquivos locais preexistentes e a pesquisa já entregue.
- Manter código e dados operacionais nos caminhos atuais; documentação em português.
- Sprint 2: Fase 6, Grupo 17, Paulo Roberto Faulstich Rego, RM 572292; prazo no enunciado: 13/10/2026 às 23h59.
- Apresentação online aceita no caso do autor, conforme relato dele em 08/10/2026. Reutilizar o vídeo https://youtu.be/B1YzQmRzsfg, localizado no YouTube Studio e confirmado pelo autor nesta conversa.
- Não adicionar previsão, segmentação, Pix ou integração GoodWe por API. Explicar os desvios de escopo.
- Validar em banco local isolado. Não alterar banco existente, Supabase ou equipamento.
- Não submeter a atividade no portal. Publicação no GitHub deve usar apenas arquivos revisados.

## Foco da revisão

- Snapshot da Sprint 1: arquivos idênticos ao commit original e links internos funcionais.
- Execução a partir de banco vazio: sequência de migração, cadastro, importação e fechamento reproduzível.
- Mês padrão nos testes: independente do calendário e de escritas de outros testes.
- IA e rateio: nenhuma promessa de funcionalidade adiada ou de reprodução financeira exata onde houve mudança de política.
- Evidências e publicação: vídeo fornecido pelo autor, links acessíveis, nenhum segredo ou artefato temporário incluído.

## Task 1: Documentação e preservação

**Files:** `README.md`, `docs/sprints/sprint-01/`, `docs/sprints/sprint-02/`, `docs/entregas/sprint-02.txt`, `docs/uso_ia.md`, `apps/web/README.md`.

**Interfaces:** consome o commit publicado `46292ef2077ffeb21d15cd4196c7fafda0860514`, os enunciados e o código atual; produz os guias de avaliação e execução.

- [x] Exportar os dez arquivos do commit original para `docs/sprints/sprint-01/arquivo-original/`, preservando bytes e caminhos relativos; registrar SHA-256.
- [x] Criar índices por sprint e copiar os enunciados sem modificá-los.
- [x] Reescrever o README principal com implementação atual, limites, execução local e navegação entre as sprints.
- [x] Documentar os desvios da Sprint 1, inclusive a redução de R$ 25,00 na taxa da unidade U102.
- [x] Atualizar a identificação do TXT e registrar o uso de IA na implementação sem atribuir ao autor validações não confirmadas.
- [x] Incorporar o link do vídeo quando recebido; sem inventar URL ou status de submissão.

## Task 2: Testes de navegador

**Files:** `apps/web/e2e/auth-shell.spec.ts`, `apps/web/e2e/session-review.spec.ts`.

**Interfaces:** os testes exercitam as rotas reais de login e recargas; fixtures de períodos usam o contrato `BillingPeriodView` da API.

- [x] Usar como baseline a execução anterior: 41 aprovados e 3 falhas, duas pelo título antigo do login e uma pela ausência de períodos no fixture.
- [x] Substituir a asserção do título antigo pela presença dos campos de acesso e do botão de entrada, mantendo a verificação do redirecionamento.
- [x] No teste de período padrão, fixar o relógio em outubro e fornecer períodos de julho/agosto pela API simulada; verificar que agosto é escolhido e a URL normalizada.
- [x] Executar `pnpm test:web`; esperado: todos os testes aprovados, sem mudar código do produto.

## Task 3: Validação e publicação

**Files:** `docs/sprints/sprint-02/evidencias.md`, arquivo de entrega também em `fase-6/trabalhos/`.

**Interfaces:** consome documentação e testes corrigidos; produz evidências rastreáveis e TXT de submissão.

- [x] Reproduzir os comandos documentados com banco temporário e validar julho: 17 recargas, 167,77 kWh, 4 faturas, R$ 270,12.
- [x] Conferir links locais, integridade do snapshot e do enunciado; revisar alterações e caminhos a publicar.
- [x] Rodar Python, client, lint, tipos, build com `AUTH_MODE=supabase`, migrações e contrato; reaproveitar verificações anteriores que não foram afetadas.
- [x] Obter revisão independente do conjunto final e resolver os achados importantes.
- [ ] Com vídeo e revisão final completos, registrar commits descritivos e publicar a evolução no mesmo repositório; verificar o commit remoto.
- [ ] Entregar o TXT preparado, distinguindo publicação no GitHub de submissão no portal.

## Registro da execução

- Trabalho realizado no checkout existente para preservar as alterações locais usadas na apresentação, com backup do diff anterior e dos dois arquivos não rastreados em pasta temporária. Código do produto não foi alterado nesta preparação; os ajustes novos de código são nos testes.
- Resultado: 328 testes Python, 19 do cliente e 44 de navegador aprovados; lint/tipos/build/migrações/contrato verificados.
- Reprodução em banco novo: 17 recargas, 167,77 kWh, quatro faturas, R$ 270,12.
- Revisão independente: sem achados acionáveis no escopo.
- Vídeo confirmado pelo autor: https://youtu.be/B1YzQmRzsfg (3min54s, não listado, enviado em 02/09/2026). Link incorporado aos READMEs, às evidências e às duas cópias do TXT.
- Publicação final no GitHub em preparação; submissão no portal não realizada nesta tarefa.
