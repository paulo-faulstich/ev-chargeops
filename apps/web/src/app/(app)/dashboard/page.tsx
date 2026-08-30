const closeStages = ["Evidência", "Atribuição", "Custos", "Fechamento"];

export default function DashboardPage() {
  return (
    <div className="dashboard-foundation">
      <header className="workspace-header">
        <div>
          <p className="utility-label">Fechamento / visão geral</p>
          <h1>Visão operacional</h1>
          <p className="workspace-lede">
            Um único percurso para transformar sessões do carregador em
            cobranças compreensíveis e auditáveis.
          </p>
        </div>
        <div className="checkpoint-marker">
          <span className="marker-code">A</span>
          <p>
            <span>Checkpoint</span>
            Fundação operacional
          </p>
        </div>
      </header>

      <section className="close-flow" aria-labelledby="close-flow-title">
        <div className="section-heading">
          <p className="utility-label">Circuito de fechamento</p>
          <h2 id="close-flow-title">Do registro à decisão</h2>
        </div>

        <ol className="circuit-spine">
          {closeStages.map((stage, index) => (
            <li key={stage} className={index === 0 ? "current" : undefined}>
              <span className="circuit-node" aria-hidden="true" />
              <span className="stage-index">0{index + 1}</span>
              <span className="stage-name">{stage}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="empty-forward" aria-labelledby="next-checkpoint-title">
        <div className="empty-rule" aria-hidden="true" />
        <div>
          <p className="utility-label">Próximo checkpoint</p>
          <h2 id="next-checkpoint-title">O fechamento ganha contexto.</h2>
          <p>
            Totais do período, moradores, fila de ações e prontidão para
            fechamento aparecerão aqui a partir dos dados persistidos — sem
            esconder origem ou pendências.
          </p>
        </div>
        <LinkHint />
      </section>
    </div>
  );
}

function LinkHint() {
  return (
    <div className="foundation-note">
      <span className="note-line" aria-hidden="true" />
      <p>
        Enquanto isso, as exportações do SEMS+ permanecem em
        <strong> Fontes de dados</strong>, como apoio ao produto — não como
        destino principal.
      </p>
    </div>
  );
}
