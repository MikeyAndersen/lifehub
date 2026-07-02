/* Fælles kort-skal: label venstre (evt. med chip), meta/handling højre. */
export default function Card({ label, chip, meta, children }) {
  return (
    <section className="card">
      <div className="card-head">
        <div className="card-label-group">
          <span className="card-label">{label}</span>
          {chip && <span className="chip">{chip}</span>}
        </div>
        {meta}
      </div>
      {children}
    </section>
  );
}
