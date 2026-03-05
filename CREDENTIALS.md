# Database Credentials

**⚠️ KEEP THIS FILE SECURE - DO NOT COMMIT TO GIT**

This file is already in `.gitignore` for your protection.

---

## PostgreSQL Database Credentials

### Database Information
- **Host**: localhost
- **Port**: 5432
- **Database Name**: stock_analysis
- **Username**: stock_user
- **Password**: StockAnalysis2025!

### Connection String
```
postgresql://stock_user:StockAnalysis2025!@localhost:5432/stock_analysis
```

### Environment File Location
```
/Users/barunshrestha/repo/Agents/ai_stock_analysis/.env
```

---

## Direct Database Access

### Using psql Command Line
```bash
psql -U stock_user -d stock_analysis -h localhost
```

When prompted, enter password: `StockAnalysis2025!`

### Common Commands
```sql
-- List all tables
\dt

-- View stock data
SELECT * FROM stock_data LIMIT 10;

-- View stock info
SELECT * FROM stock_info;

-- Count cached records
SELECT symbol, COUNT(*) as records 
FROM stock_data 
GROUP BY symbol;

-- Exit psql
\q
```

---

## PostgreSQL Service Management

### Start Service
```bash
brew services start postgresql@15
```

### Stop Service
```bash
brew services stop postgresql@15
```

### Restart Service
```bash
brew services restart postgresql@15
```

### Check Status
```bash
brew services list | grep postgresql
pg_isready
```

---

## Changing Password (Optional)

If you want to change the database password:

```bash
# Connect as your current user
psql postgres

# Run in psql:
ALTER USER stock_user WITH PASSWORD 'your_new_password';
\q

# Update .env file with new password
nano .env
```

---

## Database Backup

### Create Backup
```bash
pg_dump -U stock_user -d stock_analysis -h localhost > backup_$(date +%Y%m%d).sql
```

### Restore from Backup
```bash
psql -U stock_user -d stock_analysis -h localhost < backup_20251016.sql
```

---

## Security Best Practices

1. ✅ `.env` file is in `.gitignore` (already configured)
2. ✅ Database is localhost-only (no external access)
3. ⚠️ Consider changing password if sharing code
4. ⚠️ Never commit credentials to version control
5. ⚠️ Use stronger password for production environments

---

**Last Updated**: October 16, 2025  
**Created During**: Initial project setup

