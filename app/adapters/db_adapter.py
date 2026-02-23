import asyncpg
import os
from typing import List, Dict, Any

class SubscriberDatabase:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")

    async def get_verified_subscribers(self, exclude_issue: str = None) -> List[Dict[str, Any]]:
        """
        Fetches all verified subscribers. 
        If exclude_issue is provided, filters out those who already received that issue.
        """
        if not self.database_url:
            raise ValueError("DATABASE_URL is not set.")

        conn = await asyncpg.connect(self.database_url)
        try:
            if exclude_issue:
                # Query subscribers who HAVEN'T received this specific issue
                rows = await conn.fetch(
                    '''
                    SELECT s.email, s.identity 
                    FROM newsletter_subscribers s
                    LEFT JOIN newsletter_sent_logs l ON s.email = l.email AND l.issue_number = $1
                    WHERE s.is_verified = true AND l.id IS NULL
                    ''',
                    exclude_issue
                )
            else:
                rows = await conn.fetch(
                    'SELECT email, identity FROM newsletter_subscribers WHERE is_verified = true'
                )
            return [dict(row) for row in rows]
        finally:
            await conn.close()

    async def record_sent_emails(self, emails: List[str], issue_number: str):
        """
        Records successful sends in the logs to prevent duplicates.
        """
        if not self.database_url or not emails:
            return

        conn = await asyncpg.connect(self.database_url)
        try:
            # Bulk insert using executemany for efficiency
            data = [(email, issue_number) for email in emails]
            await conn.executemany(
                '''
                INSERT INTO newsletter_sent_logs (email, issue_number) 
                VALUES ($1, $2)
                ON CONFLICT (email, issue_number) DO NOTHING
                ''',
                data
            )
        finally:
            await conn.close()

    async def get_subscriber_stats(self, current_issue: str = None) -> Dict[str, int]:
        """
        Gets counts of subscribers by identity.
        """
        if not self.database_url:
            raise ValueError("DATABASE_URL is not set.")

        conn = await asyncpg.connect(self.database_url)
        try:
            stats = {}
            # Total verified
            total = await conn.fetchval('SELECT COUNT(*) FROM newsletter_subscribers WHERE is_verified = true')
            stats['total_verified'] = total

            # Already sent this issue
            if current_issue:
                sent_count = await conn.fetchval(
                    'SELECT COUNT(*) FROM newsletter_sent_logs WHERE issue_number = $1',
                    current_issue
                )
                stats['already_sent'] = sent_count

            # By identity
            rows = await conn.fetch(
                'SELECT identity, COUNT(*) as count FROM newsletter_subscribers WHERE is_verified = true GROUP BY identity'
            )
            for row in rows:
                stats[row['identity'] or 'unknown'] = row['count']
            
            return stats
        finally:
            await conn.close()
