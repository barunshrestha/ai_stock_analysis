import {
  Bot,
  BrainCircuit,
  Briefcase,
  CandlestickChart,
  LineChart,
  PiggyBank,
  Settings2,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  /** Marks the route as active for any nested path (e.g. /stocks/AAPL). */
  matchPrefix: string;
  /** Show in the mobile bottom tab bar (max 5). */
  mobile: boolean;
  /** Signed-in only; shows a lock for signed-out visitors (the page layout redirects to sign-in). */
  requiresAuth: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { title: "Stocks", href: "/stocks", icon: CandlestickChart, matchPrefix: "/stocks", mobile: true, requiresAuth: false },
  { title: "Portfolio", href: "/portfolio", icon: Briefcase, matchPrefix: "/portfolio", mobile: true, requiresAuth: true },
  { title: "DCA", href: "/dca", icon: PiggyBank, matchPrefix: "/dca", mobile: true, requiresAuth: true },
  { title: "Options", href: "/options", icon: LineChart, matchPrefix: "/options", mobile: true, requiresAuth: true },
  { title: "AI Analysis", href: "/ai", icon: BrainCircuit, matchPrefix: "/ai", mobile: true, requiresAuth: false },
  { title: "Automation", href: "/automation", icon: Bot, matchPrefix: "/automation", mobile: false, requiresAuth: true },
  { title: "Industries", href: "/admin/industries", icon: Settings2, matchPrefix: "/admin", mobile: false, requiresAuth: true },
];
