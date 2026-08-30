import { permanentRedirect } from "next/navigation";

export default function NewImportPage() {
  permanentRedirect("/settings/data-sources");
}
