"use client";

import { useState } from "react";

interface RepoInputProps {
  onSubmit: (repo: string) => void;
  loading: boolean;
  currentRepo: string;
}

export default function RepoInput({ onSubmit, loading, currentRepo }: RepoInputProps) {
  const [repo, setRepo] = useState(currentRepo);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = repo.trim();
    if (trimmed && trimmed.includes("/")) {
      onSubmit(trimmed);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3 items-end">
      <div className="flex-1">
        <label htmlFor="repo" className="block text-sm font-medium text-gray-700 mb-1">
          GitHub Repository
        </label>
        <input
          id="repo"
          type="text"
          value={repo}
          onChange={(e) => setRepo(e.target.value)}
          placeholder="owner/repo (e.g. facebook/react)"
          className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 focus:outline-none transition-colors"
        />
      </div>
      <button
        type="submit"
        disabled={loading || !repo.trim().includes("/")}
        className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? "Loading..." : "Load Issues"}
      </button>
    </form>
  );
}
