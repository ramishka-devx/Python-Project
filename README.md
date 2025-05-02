<p align="center">
  <a href="https://cse40.cse.uom.lk/codejam" target="blank"><img src="https://firebasestorage.googleapis.com/v0/b/profile-image-1c78a.appspot.com/o/codejam%2FCodeJameLogo.webp?alt=media&token=507a7f7b-e735-4952-ad04-d0a8f48a8f55" width="350" alt="CodeJam Logo" /></a>
</p>

# Banking API - Coding Competition

A Flask-based REST API for a simple banking application.

## Setup Instructions (Windows)

1. Clone the repository
2. Ensure you have Python 3.12 or above installed. You can check your Python version with:
```
python --version
```
3. Create a virtual environment:
```
python -m venv venv
venv\Scripts\activate
```
4. Install dependencies:
```
pip install -r requirements.txt
```
5. Initialize the database:
```
flask init-db
```
6. Run the application:
```
flask run
```
7. Open swagger UI:
```
http://localhost:5000/apidocs/
```

## API Endpoints

### Authentication
- POST /api/auth/register - Register a new user
- POST /api/auth/login - Login and get JWT token
- POST /api/auth/refresh - Refresh access token using refresh token
- POST /api/auth/logout - Logout and revoke JWT token
- POST /api/auth/verify - Verify if a token is valid and not expired
- POST /api/auth/change-password - Change the user's password
- GET /api/auth/profile - Get the authenticated user's profile

### Admin
- GET /api/auth/users - Retrieve a list of all users (Admin-only)
- DELETE /api/auth/user/{user_id} - Delete a user by ID (Admin-only)

### Accounts
- GET /api/accounts - List all accounts for the authenticated user
- POST /api/accounts - Create a new account
- GET /api/accounts/{account_id} - Get details of a specific account
- PUT /api/accounts/{account_id} - Update details of a specific account
- DELETE /api/accounts/{account_id} - Delete a specific account
- GET /api/accounts/{account_id}/transactions - Get transactions for a specific account

### Transactions
- GET /api/transactions - Get transaction history for all user accounts
- GET /api/transactions/accounts/{account_id}/transactions - Get transactions for a specific account
- POST /api/transactions/accounts/{account_id}/transactions - Create a transaction for a specific account
- POST /api/transactions/deposit - Deposit funds into an account
- POST /api/transactions/withdraw - Withdraw funds from an account
- POST /api/transactions/transfer - Transfer funds between accounts
- POST /api/transactions/transfer-advanced - Advanced transfer between accounts
