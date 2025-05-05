# Deploying Binance Grid Bot to DigitalOcean

This guide walks you through deploying your Binance Grid Bot to DigitalOcean App Platform in a region where Binance API is accessible (like Singapore).

## Prerequisites

1. A DigitalOcean account - [Sign up here](https://www.digitalocean.com/)
2. A GitHub account - [Sign up here](https://github.com/)
3. Your project code pushed to a GitHub repository

## Step 1: Push Your Code to GitHub

1. Create a new GitHub repository.
2. Push your code to the repository:

```bash
# Initialize Git repository (if not already done)
git init
git add .
git commit -m "Initial commit"

# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

## Step 2: Create a DigitalOcean App

1. Log in to your DigitalOcean account.
2. Go to the App Platform section.
3. Click on "Create App".
4. Select GitHub as the source.
5. Connect your GitHub account if needed.
6. Select the repository you pushed your code to.
7. Select the branch (usually "main").
8. Click on "Next".

## Step 3: Configure Your App

1. Choose "Web Service" as the component type.
2. Select the Singapore region (sgp) to ensure access to Binance API.
3. Keep the build command as `pip install -r requirements.txt`.
4. Set the run command to `gunicorn --worker-tmp-dir /dev/shm main:app`.
5. Set HTTP port to 8080.
6. Click on "Next".

## Step 4: Add a Database

1. Click on "Add Resource".
2. Select "Database".
3. Choose "PostgreSQL".
4. Select a suitable plan (Dev Database is fine for starting).
5. Click on "Create and Attach".
6. DigitalOcean will create a PostgreSQL database and automatically add the DATABASE_URL environment variable.

## Step 5: Add Environment Variables

1. In the Environment Variables section, ensure that DATABASE_URL is set to ${db.DATABASE_URL}.
2. Add any other environment variables you need for your application.

## Step 6: Review and Launch

1. Review your configuration.
2. Click on "Create Resources".
3. Wait for the deployment to complete (this may take a few minutes).

## Step 7: Configure Your Database (Optional)

If you need to set up your database schema:

1. Go to the Console section of your app.
2. Open a shell.
3. Run your database migrations if needed:
   ```
   python -c "from app import db; db.create_all()"
   ```

## Step 8: Access Your App

1. Once deployment is complete, click on the URL provided by DigitalOcean to access your app.
2. Log in to your app.
3. Go to the Settings page and add your Binance API keys.
4. Make sure to add the IP address of your DigitalOcean app to the whitelist in your Binance API settings.

## Step 9: Monitoring and Maintenance

1. Monitor your app's performance in the DigitalOcean dashboard.
2. Set up alerts for potential issues.
3. Check logs regularly to ensure everything is running smoothly.

## Troubleshooting

- If you encounter database connection issues, check that your DATABASE_URL environment variable is correctly set.
- If Binance API access fails, verify that:
  - Your app is deployed in a region where Binance API is accessible (Singapore is recommended).
  - Your Binance API keys are correct.
  - The app's IP address is whitelisted in your Binance API settings.
  - There are no regional restrictions for your particular account.

## Additional Resources

- [DigitalOcean App Platform Documentation](https://docs.digitalocean.com/products/app-platform/)
- [Setting up PostgreSQL on DigitalOcean](https://docs.digitalocean.com/products/databases/postgresql/)
- [Binance API Documentation](https://binance-docs.github.io/apidocs/)