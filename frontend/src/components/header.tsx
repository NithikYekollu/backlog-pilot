"use client";

export default function Header() {
  return (
    <>
      {/* Demo mode banner */}
      <div className="bg-indigo-600 text-white text-center py-1.5 text-xs font-medium tracking-wide">
        Demo &mdash; Powered by{" "}
        <a
          href="https://devin.ai"
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2 hover:text-indigo-200 transition-colors"
        >
          Devin API
        </a>
        {" "}&middot; Built for FinServ Co
      </div>
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white font-bold text-sm">
                BP
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Backlog Pilot</h1>
                <p className="text-xs text-gray-500">AI-powered issue triage & resolution</p>
              </div>
            </div>
            <a
              href="https://devin.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              Powered by Devin
            </a>
          </div>
        </div>
      </header>
    </>
  );
}
