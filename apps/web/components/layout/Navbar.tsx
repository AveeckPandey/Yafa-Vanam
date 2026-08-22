"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type FocusEvent,
} from "react";
import AnnouncementBar from "./AnnouncementBar";
import MegaMenu, { type MegaMenuKey } from "./MegaMenu";
import MobileMenu from "./MobileMenu";
import { useAuth } from "@/components/auth/AuthProvider";

type MenuTrigger = {
  label: string;
  key: MegaMenuKey;
};

const menuTriggers: MenuTrigger[] = [
  { label: "Skin Care", key: "skincare" },
  { label: "Make Up", key: "makeup" },
  { label: "Body Care", key: "body" },
  { label: "Fragrance", key: "fragrance" },
];

function Wordmark() {
  return (
    <span className="wordmark" aria-hidden="true">
      <span>YAFA</span>
      <span>VANAM</span>
    </span>
  );
}

function ActionIcon({ type }: { type: "search" | "account" | "bag" }) {
  return <span className={`ui-icon ui-icon--${type}`} aria-hidden="true" />;
}

export default function Navbar() {
  const pathname = usePathname();
  const headerRef = useRef<HTMLElement>(null);
  const mobileButtonRef = useRef<HTMLButtonElement>(null);
  const [activeMenu, setActiveMenu] = useState<MegaMenuKey | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [bagCount, setBagCount] = useState(0);
  const { isAuthenticated, isLoading, openAuth, logout } = useAuth();

  const closeDesktopMenu = useCallback(() => setActiveMenu(null), []);

  const focusFirstMenuLink = useCallback((menu: MegaMenuKey) => {
    setActiveMenu(menu);
    window.requestAnimationFrame(() => {
      document.querySelector<HTMLAnchorElement>("#desktop-mega-menu a")?.focus();
    });
  }, []);

  const handleTriggerKeyDown = (
    event: ReactKeyboardEvent<HTMLButtonElement>,
    menu: MegaMenuKey,
  ) => {
    if (event.key !== "ArrowDown" && event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    focusFirstMenuLink(menu);
  };

  const closeMobileMenu = useCallback(() => {
    setMobileOpen(false);
    window.requestAnimationFrame(() => mobileButtonRef.current?.focus());
  }, []);

  useEffect(() => {
    setActiveMenu(null);
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (isLoading) return;
    const updateBagCount = (event?: Event) => {
      const detail = (event as CustomEvent<{ itemCount?: number }> | undefined)?.detail;
      if (typeof detail?.itemCount === "number") {
        setBagCount(detail.itemCount);
        return;
      }
      fetch("/api/cart", { credentials: "include", cache: "no-store" })
        .then((response) => response.ok ? response.json() : Promise.reject())
        .then((cart) => setBagCount(Number(cart.itemCount) || 0))
        .catch(() => setBagCount(0));
    };

    updateBagCount();
    window.addEventListener("yafa-cart-updated", updateBagCount);
    return () => {
      window.removeEventListener("yafa-cart-updated", updateBagCount);
    };
  }, [isAuthenticated, isLoading]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (!headerRef.current?.contains(event.target as Node)) {
        setActiveMenu(null);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !activeMenu) return;
      event.preventDefault();
      const trigger = document.getElementById(`nav-trigger-${activeMenu}`);
      setActiveMenu(null);
      trigger?.focus();
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [activeMenu]);

  const handleHeaderBlur = (event: FocusEvent<HTMLElement>) => {
    if (!headerRef.current?.contains(event.relatedTarget as Node | null)) {
      setActiveMenu(null);
    }
  };

  return (
    <header
      className="site-header"
      id="site-header"
      ref={headerRef}
      onMouseLeave={closeDesktopMenu}
      onBlur={handleHeaderBlur}
    >
      <AnnouncementBar />

      <div className="utility-nav" aria-label="YAFA VANAM collections and services">
        <div className="utility-nav__collections">
          <Link className="utility-nav__active" href="/">YAFA VANAM</Link>
          <Link href="/makeup?category=complexion">EARTH SKIN</Link>
          <Link href="/makeup?category=lips">PETAL VELVET</Link>
          <Link href="/fragrance">NOCTURNE</Link>
        </div>

        <div className="utility-nav__actions">
          <Link href="/search" aria-label="Search">
            <ActionIcon type="search" />
          </Link>
          <button type="button" aria-label={isAuthenticated ? "Sign out" : "Sign in"} onClick={() => isAuthenticated ? void logout() : openAuth()}>
            <ActionIcon type="account" />
          </button>
          <button className="utility-nav__bag-button" type="button" aria-label={`Open shopping bag, ${bagCount} ${bagCount === 1 ? "item" : "items"}`} onClick={() => window.dispatchEvent(new Event("yafa-cart-open"))}>
            <ActionIcon type="bag" />
            <span className="utility-nav__bag-count" aria-hidden="true">{bagCount}</span>
          </button>
          <Link className="utility-nav__contact" href="/contact">
            Stay in touch
          </Link>
        </div>
      </div>

      <nav className="primary-nav" aria-label="Main navigation">
        <div className="primary-nav__brand-slot">
          <Link
            className="primary-nav__brand"
            href="/"
            aria-label="YAFA VANAM home"
            data-logo-target
          >
            <Wordmark />
          </Link>
        </div>

        <div className="primary-nav__desktop">
          <Link className="primary-nav__link" href="/shop">
            Shop All
          </Link>

          {menuTriggers.map((item) => (
            <button
              className="primary-nav__trigger"
              id={`nav-trigger-${item.key}`}
              key={item.key}
              type="button"
              aria-expanded={activeMenu === item.key}
              aria-controls="desktop-mega-menu"
              onClick={() => setActiveMenu(item.key)}
              onMouseEnter={() => setActiveMenu(item.key)}
              onFocus={() => setActiveMenu(item.key)}
              onKeyDown={(event) => handleTriggerKeyDown(event, item.key)}
            >
              {item.label}
            </button>
          ))}

          <Link className="primary-nav__kit" href="/build-my-kit">
            Build My Kit
          </Link>
        </div>

        <div className="primary-nav__mobile-actions">
          <Link href="/search" aria-label="Search">
            <ActionIcon type="search" />
          </Link>
          <button className="primary-nav__mobile-bag" type="button" aria-label={`Open shopping bag, ${bagCount} ${bagCount === 1 ? "item" : "items"}`} onClick={() => window.dispatchEvent(new Event("yafa-cart-open"))}>
            <ActionIcon type="bag" />
            {bagCount > 0 ? <span className="primary-nav__mobile-bag-count" aria-hidden="true">{bagCount}</span> : null}
          </button>
          <button
            className="menu-toggle"
            type="button"
            ref={mobileButtonRef}
            aria-label="Open navigation"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen(true)}
          >
            <span aria-hidden="true" />
            <span aria-hidden="true" />
          </button>
        </div>
      </nav>

      {activeMenu && (
        <MegaMenu
          activeMenu={activeMenu}
          labelledBy={`nav-trigger-${activeMenu}`}
          onNavigate={closeDesktopMenu}
        />
      )}

      <MobileMenu open={mobileOpen} onClose={closeMobileMenu} />
    </header>
  );
}
