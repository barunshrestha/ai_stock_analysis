import {
  Bot,
  BrainCircuit,
  Briefcase,
  CandlestickChart,
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
}

export const NAV_ITEMS: NavItem[] = [
  { title: "Stocks", href: "/stocks", icon: CandlestickChart, matchPrefix: "/stocks", mobile: true },
  { title: "Portfolio", href: "/portfolio", icon: Briefcase, matchPrefix: "/portfolio", mobile: true },
  { title: "DCA", href: "/dca", icon: PiggyBank, matchPrefix: "/dca", mobile: true },
  { title: "AI Analysis", href: "/ai", icon: BrainCircuit, matchPrefix: "/ai", mobile: true },
  { title: "Automation", href: "/automation", icon: Bot, matchPrefix: "/automation", mobile: true },
  { title: "Industries", href: "/admin/industries", icon: Settings2, matchPrefix: "/admin", mobile: false },
];
