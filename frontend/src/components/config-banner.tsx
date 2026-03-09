"use client";

interface ConfigBannerProps {
  hasApiKeys: boolean;
}

export default function ConfigBanner({ hasApiKeys }: ConfigBannerProps) {
  if (hasApiKeys) return null;

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 text-amber-500 text-lg">&#9888;</div>
        <div>
          <h3 className="text-sm font-semibold text-amber-800">
            API Keys Not Configured
          </h3>
          <p className="text-sm text-amber-700 mt-1">
            Set <code className="bg-amber-100 px-1 rounded text-xs">DEVIN_API_KEY</code> and
            optionally <code className="bg-amber-100 px-1 rounded text-xs">GITHUB_TOKEN</code> in
            the backend <code className="bg-amber-100 px-1 rounded text-xs">.env</code> file to
            enable triage and fix actions. GitHub issues from public repos can still be browsed
            without a token.
          </p>
        </div>
      </div>
    </div>
  );
}
