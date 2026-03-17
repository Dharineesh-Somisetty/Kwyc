import kwycLockup from '../assets/kwyc-logo.png';

const BrandMark = ({ className = '' }) => (
  <svg
    viewBox="0 0 180 180"
    className={className}
    aria-hidden="true"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <circle cx="114" cy="58" r="34" stroke="#2BBFD1" strokeWidth="8" />
    <path
      d="M134 79l16 16"
      stroke="#2BBFD1"
      strokeWidth="8"
      strokeLinecap="round"
    />
    <rect x="38" y="42" width="34" height="76" rx="2" fill="#F6FBF4" stroke="#0F5B24" strokeWidth="6" />
    {[
      48, 56, 64, 72, 80, 88, 96, 104,
    ].map((y, index) => (
      <path
        key={y}
        d={`M46 ${y}h18${index % 2 === 0 ? '' : ' M46 ' + (y + 4) + 'h12'}`}
        stroke="#0F5B24"
        strokeWidth="4"
        strokeLinecap="round"
      />
    ))}
    <path
      d="M71 109V48c19 0 31 5 40 14 8-4 17-6 28-6v15c-11 0-21 2-28 10v28c0 17 11 27 29 27v15c-17 0-29-5-38-16-8 10-19 16-33 16v-15c18 0 29-11 29-27Z"
      fill="#F6FBF4"
      stroke="#0F5B24"
      strokeWidth="8"
      strokeLinejoin="round"
    />
    <path
      d="M92 88c14-25 32-33 47-33-1 16-5 39-31 53-7 4-17 4-26 2 4-7 7-14 10-22Z"
      fill="#6BCB5A"
      stroke="#0F5B24"
      strokeWidth="6"
      strokeLinejoin="round"
    />
    <path
      d="M115 61c-8 8-19 24-36 58"
      stroke="#F6FBF4"
      strokeWidth="6"
      strokeLinecap="round"
    />
    <circle cx="113" cy="67" r="2.8" fill="#0F5B24" />
    <circle cx="122" cy="63" r="2.8" fill="#0F5B24" />
    <circle cx="122" cy="74" r="2.8" fill="#0F5B24" />
    <circle cx="131" cy="68" r="2.8" fill="#0F5B24" />
    <circle cx="129" cy="79" r="2.8" fill="#0F5B24" />
    <path
      d="M116 106c9 0 17 7 17 16 0 10-8 18-18 18-8 0-15-4-18-11"
      fill="#6BCB5A"
      stroke="#0F5B24"
      strokeWidth="6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M131 100c2 4 2 9 0 13"
      stroke="#0F5B24"
      strokeWidth="6"
      strokeLinecap="round"
    />
    <path
      d="M125 122c-3 2-5 5-5 9"
      stroke="#0F5B24"
      strokeWidth="4"
      strokeLinecap="round"
    />
  </svg>
);

export default function BrandLogo({
  variant = 'lockup',
  className = '',
  showTagline = false,
}) {
  if (variant === 'icon') {
    return <BrandMark className={className} />;
  }

  if (showTagline) {
    return (
      <img
        src={kwycLockup}
        alt="KWYC logo"
        className={`w-full max-w-[22rem] sm:max-w-[26rem] mx-auto ${className}`.trim()}
      />
    );
  }

  return (
    <div className={`flex flex-col items-center text-center ${className}`.trim()}>
      <BrandMark className="h-28 w-28 sm:h-32 sm:w-32" />
      <div className="mt-3">
        <div className="font-display text-4xl sm:text-5xl font-extrabold tracking-tight text-[#145C2B]">
          KWYC
        </div>
        {showTagline && (
          <p className="mt-1 text-sm sm:text-base font-medium text-[#2B6A39]">
            Know What You Consume
          </p>
        )}
      </div>
    </div>
  );
}
