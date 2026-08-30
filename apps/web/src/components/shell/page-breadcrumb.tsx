export function PageBreadcrumb({
  section,
  current,
}: {
  section: string;
  current: string;
}) {
  return (
    <nav className="page-breadcrumb" aria-label="Breadcrumb">
      <ol>
        <li>{section}</li>
        <li aria-hidden="true">/</li>
        <li aria-current="page">{current}</li>
      </ol>
    </nav>
  );
}
