import { useId } from 'react'

export default function BrandLogo({ size = 34 }) {
  const gradId = useId()

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradId} x1="4" y1="4" x2="44" y2="44" gradientUnits="userSpaceOnUse">
          <stop stopColor="#12a37c" />
          <stop offset="1" stopColor="#0b6b4e" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="44" height="44" rx="13" fill={`url(#${gradId})`} />
      <path
        d="M12 29c0-7.5 5.5-12 12-12s12 4.5 12 12"
        stroke="#ffffff"
        strokeWidth="3.4"
        strokeLinecap="round"
        fill="none"
      />
      <path d="M15 29h18" stroke="#ffffff" strokeWidth="3.4" strokeLinecap="round" />
      <path
        d="M32.4 10.8l1.1 2.7 2.7 1.1-2.7 1.1-1.1 2.7-1.1-2.7-2.7-1.1 2.7-1.1 1.1-2.7z"
        fill="#bff0df"
      />
    </svg>
  )
}
