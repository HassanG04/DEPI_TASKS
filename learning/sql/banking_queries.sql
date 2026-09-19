/*
  DEPI SQL Server practice
  ------------------------
  These queries target the classroom banking schema (Customer, Account,
  Transactions, Loans). They demonstrate the SQL concepts practised during
  DEPI; a portable schema and fixture are a future improvement.
*/

-- String functions and aliases.
SELECT
    UPPER(Name) AS UpperName,
    LOWER(Name) AS LowerName,
    LEFT(Name, LEN(Name) - 2) AS NameWithoutLastTwoCharacters
FROM Customer;

-- Null handling.
SELECT
    CustomerID,
    COALESCE(Email, 'NoEmail') AS Email
FROM Customer;

-- Date functions.
SELECT
    DATENAME(month, TransactionDate) AS TransactionMonth,
    DATEPART(year, TransactionDate) AS TransactionYear
FROM Transactions;

-- CTE plus a ranking window. RANK keeps tied balances in the top three ranks.
WITH RankedAccounts AS (
    SELECT
        AccountID,
        Balance,
        RANK() OVER (ORDER BY Balance DESC) AS BalanceRank
    FROM Account
)
SELECT AccountID, Balance, BalanceRank
FROM RankedAccounts
WHERE BalanceRank <= 3
ORDER BY BalanceRank, AccountID;

-- Join related entities.
SELECT
    c.CustomerID,
    c.Name,
    a.AccountID,
    a.Balance
FROM Customer AS c
INNER JOIN Account AS a
    ON a.CustomerID = c.CustomerID;

-- Scalar function: return the month name for a transaction date.
GO
CREATE OR ALTER FUNCTION dbo.GetMonthName (@TransactionDate date)
RETURNS nvarchar(30)
AS
BEGIN
    RETURN DATENAME(month, @TransactionDate);
END;
GO

-- Inline table-valued function: return account information for one customer.
CREATE OR ALTER FUNCTION dbo.GetCustomerAccounts (@CustomerID int)
RETURNS TABLE
AS
RETURN (
    SELECT
        c.Name AS CustomerName,
        a.AccountID,
        a.Balance
    FROM Customer AS c
    INNER JOIN Account AS a
        ON a.CustomerID = c.CustomerID
    WHERE c.CustomerID = @CustomerID
);
GO

-- Multi-statement table-valued function: accounts in a supplied balance range.
CREATE OR ALTER FUNCTION dbo.GetAccountsByBalanceRange (
    @MinimumBalance decimal(18, 2),
    @MaximumBalance decimal(18, 2)
)
RETURNS @Accounts TABLE (
    AccountID int PRIMARY KEY,
    Balance decimal(18, 2)
)
AS
BEGIN
    INSERT INTO @Accounts (AccountID, Balance)
    SELECT AccountID, Balance
    FROM Account
    WHERE Balance BETWEEN @MinimumBalance AND @MaximumBalance;

    RETURN;
END;
GO
