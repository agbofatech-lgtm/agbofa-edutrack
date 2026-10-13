type BrandMarkProps = {
  compact?: boolean
  inverse?: boolean
}

export function BrandMark({
  compact = false,
  inverse = false,
}: BrandMarkProps) {
  return (
    <div
      className={`flex items-center gap-3 ${inverse ? 'text-white' : 'text-ink'}`}
    >
      <span
        aria-hidden="true"
        className="bg-forest-900 grid size-11 shrink-0 place-items-center rounded-2xl text-lg font-bold text-white shadow-sm"
      >
        A
      </span>
      {!compact && (
        <span className="min-w-0">
          <span className="block text-sm font-extrabold tracking-[0.12em]">
            AGBOFA
          </span>
          <span
            className={`block text-xs font-medium ${inverse ? 'text-white/75' : 'text-muted'}`}
          >
            EduTrack
          </span>
        </span>
      )}
    </div>
  )
}
