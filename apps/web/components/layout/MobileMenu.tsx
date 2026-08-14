"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

type MobileMenuProps = {
  open: boolean;
  onClose: () => void;
};

const mobileGroups = [
  {
    label: "Skin Care",
    links: [
      { label: "Cleansers", href: "/skincare?category=cleansers" },
      { label: "Serums", href: "/skincare?category=serums" },
      { label: "Moisturisers", href: "/skincare?category=moisturisers" },
      { label: "Eye care", href: "/skincare?category=eye-care" },
      { label: "All skincare", href: "/skincare" },
    ],
  },
  {
    label: "Make Up",
    links: [
      { label: "Complexion", href: "/makeup?category=complexion" },
      { label: "Lips", href: "/makeup?category=lips" },
      { label: "Cheeks", href: "/makeup?category=cheeks" },
      { label: "Eyes", href: "/makeup?category=eyes" },
      { label: "All makeup", href: "/makeup" },
    ],
  },
  {
    label: "Body Care",
    links: [
      { label: "Body cleansers", href: "/body-care?category=cleansers" },
      { label: "Body moisturisers", href: "/body-care?category=moisturisers" },
      { label: "Hair care", href: "/body-care?category=hair" },
      { label: "All body care", href: "/body-care" },
    ],
  },
];

export default function MobileMenu({ open, onClose }: MobileMenuProps) {
  const panelRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== "Tab" || !panelRef.current) return;

      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), summary, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => !element.hasAttribute("disabled"));

      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div className="mobile-menu-layer">
      <button
        className="mobile-menu-layer__backdrop"
        type="button"
        onClick={onClose}
        aria-label="Close navigation"
      />
      <nav
        className="mobile-menu"
        ref={panelRef}
        aria-label="Mobile navigation"
        aria-modal="true"
        role="dialog"
      >
        <div className="mobile-menu__header">
          <span className="mobile-menu__wordmark" aria-hidden="true">
            <span>YAFA</span>
            <span>VANAM</span>
          </span>
          <button
            className="mobile-menu__close"
            type="button"
            onClick={onClose}
            ref={closeButtonRef}
            aria-label="Close navigation"
          >
            <span aria-hidden="true">×</span>
          </button>
        </div>

        <div className="mobile-menu__primary">
          <Link href="/shop" onClick={onClose}>
            Shop All
          </Link>

          {mobileGroups.map((group, index) => (
            <details key={group.label} open={index === 0}>
              <summary>
                {group.label}
                <span aria-hidden="true">+</span>
              </summary>
              <ul>
                {group.links.map((link) => (
                  <li key={link.label}>
                    <Link href={link.href} onClick={onClose}>
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </details>
          ))}

          <Link href="/fragrance" onClick={onClose}>
            Fragrance
          </Link>
        </div>

        <Link className="mobile-menu__advisor" href="/build-my-kit" onClick={onClose}>
          Build My Kit
        </Link>

        <div className="mobile-menu__utility">
          <Link href="/search" onClick={onClose}>Search</Link>
          <Link href="/account" onClick={onClose}>My account</Link>
          <Link href="/cart" onClick={onClose}>Shopping bag</Link>
          <Link href="/contact" onClick={onClose}>Stay in touch</Link>
        </div>
      </nav>
    </div>
  );
}
