/**
 * HowToUsePage – guides users through how to use the KWYC app.
 * Covers barcode scanning, nutrition label uploads, and what a nutrition label is.
 */

export default function HowToUsePage({ onBack }) {
  return (
    <div className="min-h-screen bg-bg1 text-gray-800">
      <div className="mx-auto max-w-2xl px-4 py-10">

        {/* Back button */}
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-brandDeep transition-colors mb-6 min-h-[44px]"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
          Back to Scan
        </button>

        {/* Header */}
        <div className="text-center mb-10">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-brandTint flex items-center justify-center">
            <svg className="w-8 h-8 text-brandDeep" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
            </svg>
          </div>
          <h1 className="text-2xl font-display font-extrabold gradient-text mb-2">How to Use KWYC</h1>
          <p className="text-gray-400 text-sm">Three simple ways to analyze any food or drink product</p>
        </div>

        {/* Step 1: Barcode */}
        <div className="glass-strong p-6 mb-5">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-brandTint flex items-center justify-center shrink-0 mt-0.5">
              <span className="text-brandDeep font-bold text-lg">1</span>
            </div>
            <div>
              <h3 className="font-bold text-gray-800 mb-1.5">Scan or Enter a Barcode</h3>
              <p className="text-sm text-gray-500 leading-relaxed">
                Every packaged food or drink product has a barcode (the black-and-white lines on the packaging).
                You can either <strong>scan it with your camera</strong> or <strong>type the number below the barcode</strong> manually.
              </p>
              <p className="text-sm text-gray-500 mt-2 leading-relaxed">
                If the product is in our database, you'll get instant results with a personalized health score and ingredient breakdown.
              </p>
            </div>
          </div>
        </div>

        {/* Step 2: Label upload */}
        <div className="glass-strong p-6 mb-5">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center shrink-0 mt-0.5">
              <span className="text-emerald-600 font-bold text-lg">2</span>
            </div>
            <div>
              <h3 className="font-bold text-gray-800 mb-1.5">Upload a Nutrition Label Photo</h3>
              <p className="text-sm text-gray-500 leading-relaxed">
                If the barcode isn't in our database, or if you prefer, you can <strong>take a photo</strong> of the product's
                nutrition/ingredient label or <strong>upload an image</strong> from your gallery.
              </p>
              <p className="text-sm text-gray-500 mt-2 leading-relaxed">
                Our AI will read the label and analyze every ingredient for you.
              </p>
            </div>
          </div>
        </div>

        {/* What is a nutrition label? */}
        <div className="glass-strong p-6 mb-5 border-l-4 border-l-brandSoft">
          <h3 className="font-bold text-gray-800 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-brandDeep" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
            </svg>
            What is a Nutrition Label?
          </h3>
          <p className="text-sm text-gray-500 leading-relaxed mb-3">
            A nutrition label is the panel found on packaged food and beverages — usually on the back or side of the product. It contains:
          </p>
          <ul className="space-y-2 mb-3">
            {[
              'Nutrition Facts — calories, fats, carbs, protein, sodium, etc.',
              'Ingredients List — every ingredient used, listed from most to least by weight',
              'Allergen Warnings — common allergens like milk, wheat, peanuts, soy',
            ].map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brandSoft shrink-0" />
                {item}
              </li>
            ))}
          </ul>
          <p className="text-sm text-gray-500 leading-relaxed">
            When uploading, make sure the <strong>ingredients list</strong> is clearly visible in the photo — that's the part our AI focuses on most.
          </p>
        </div>

        {/* Tips for a good photo */}
        <div className="glass-strong p-6 mb-5">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center shrink-0 mt-0.5">
              <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
              </svg>
            </div>
            <div>
              <h3 className="font-bold text-gray-800 mb-1.5">Tips for a Good Label Photo</h3>
              <ul className="space-y-1.5">
                {[
                  'Make sure the label fills most of the frame',
                  'Use good, even lighting — avoid glare and shadows',
                  'Hold steady and let the camera focus before capturing',
                  'The text should be sharp and readable, not blurry',
                  'Include the full ingredients list in the shot',
                ].map((tip, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-500">
                    <svg className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                    {tip}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Step 3: Results */}
        <div className="glass-strong p-6 mb-8">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-sky-50 flex items-center justify-center shrink-0 mt-0.5">
              <span className="text-sky-600 font-bold text-lg">3</span>
            </div>
            <div>
              <h3 className="font-bold text-gray-800 mb-1.5">Get Your Personalized Score</h3>
              <p className="text-sm text-gray-500 leading-relaxed">
                Results are tailored to your household profile. You'll see a health score,
                ingredient-by-ingredient breakdown, allergy & diet conflict flags, and you can even <strong>chat with AI</strong> to
                ask follow-up questions about any ingredient.
              </p>
              <p className="text-sm text-gray-500 mt-2 leading-relaxed">
                What's safe for one person may not be for another — that's why personalized profiles matter.
              </p>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="text-center">
          <button onClick={onBack} className="btn-primary text-sm px-8 py-3">
            Start Scanning
          </button>
        </div>
      </div>
    </div>
  );
}
