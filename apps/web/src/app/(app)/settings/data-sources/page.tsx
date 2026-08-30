import { redirect } from "next/navigation";

import { ImportDropzone } from "@/components/imports/import-dropzone";
import { PageBreadcrumb } from "@/components/shell/page-breadcrumb";
import { getAccessToken } from "@/lib/auth/access-token";

export default async function DataSourcesPage() {
  const accessToken = await getAccessToken();
  if (!accessToken) redirect("/login");

  return (
    <div className="data-sources-page">
      <header className="data-sources-header">
        <div>
          <PageBreadcrumb section="Configurações" current="Fontes de dados" />
          <h1>Fontes de dados</h1>
          <p>
            Importe registros do SEMS+ e acompanhe como os dados entram no
            ChargeOps.
          </p>
        </div>
        <div className="source-state" aria-label="Estado da integração">
          <span className="source-state-node" aria-hidden="true" />
          <p>
            <span>Integração atual</span>
            Importação assistida
          </p>
        </div>
      </header>

      <section className="source-adapter" aria-labelledby="sems-source-title">
        <div className="source-adapter-heading">
          <div>
            <p className="utility-label">Fonte conectada</p>
            <h2 id="sems-source-title">SEMS+ CSV</h2>
          </div>
          <p className="adapter-label">Adapter temporário · somente leitura</p>
        </div>

        <ImportDropzone accessToken={accessToken} />
      </section>
    </div>
  );
}
