"use client";

import { useState } from "react";

interface PasswordInputProps {
  id?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  required?: boolean;
  minLength?: number;
}

export function PasswordInput({
  id,
  value,
  onChange,
  required = false,
  minLength,
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <input
        id={id}
        type={visible ? "text" : "password"}
        value={value}
        onChange={onChange}
        required={required}
        minLength={minLength}
        className="w-full rounded-lg border border-gray-200/60 bg-white px-4 py-2.5 pr-10 text-sm text-[#2F3437] placeholder:text-gray-400 transition-all duration-150 focus:border-gray-400 focus:ring-0 focus:outline-none"
      />
      {value.length > 0 && (
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setVisible((v) => !v)}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 transition-colors"
          aria-label={visible ? "Hide password" : "Show password"}
        >
          {visible ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              className="size-4"
              aria-hidden="true"
            >
              <title>Hide password</title>
              <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0Z" />
              <circle cx="12" cy="12" r="3" />
              <line x1="2" y1="2" x2="22" y2="22" />
            </svg>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              className="size-4"
              aria-hidden="true"
            >
              <title>Show password</title>
              <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0Z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          )}
        </button>
      )}
    </div>
  );
}
