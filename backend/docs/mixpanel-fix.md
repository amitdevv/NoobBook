# Fixing Mixpanel Setup Errors

## "Service account does not have access to this Mixpanel project"

The service account exists and the credentials are correct, but it has not been granted access to the project ID you entered.

**Fix:**

1. Mixpanel → Organization Settings → Service Accounts.
2. Open the service account.
3. Under **Project Access**, add the project.
4. Set the role to **Analyst** or higher. Consumer is not enough for the Query API.
5. Save, return to NoobBook, hit Validate again. No need to regenerate the secret.
