import { IndustriesAdmin } from "@/components/admin/industries-admin";

export const metadata = { title: "Industries" };

export default function IndustriesAdminPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Industries (Admin)
        </h1>
        <p className="text-sm text-muted-foreground">
          Group stocks into custom industries. Assignments are stored in your
          PostgreSQL database.
        </p>
      </div>
      <IndustriesAdmin />
    </div>
  );
}
