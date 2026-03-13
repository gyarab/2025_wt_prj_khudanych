from django.test import TestCase
from django.contrib.auth.models import User
from .models import Profile
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError

class ProfileNicknameTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.profile = self.user.profile

    def test_nickname_change_once(self):
        self.profile.display_name = "First Nick"
        self.profile.full_clean()
        self.profile.save()
        self.assertEqual(self.profile.nickname_change_count, 1)
        self.assertIsNotNone(self.profile.last_nickname_change)

    def test_nickname_cooldown_failure(self):
        self.profile.display_name = "First Nick"
        self.profile.save()
        
        # Try to change again immediately
        self.profile.display_name = "Second Nick"
        with self.assertRaises(ValidationError) as cm:
            self.profile.full_clean()
        self.assertIn("Please wait", str(cm.exception))

    def test_nickname_cooldown_success_after_7_days(self):
        self.profile.display_name = "First Nick"
        self.profile.save()
        
        # Simulate 8 days later
        self.profile.last_nickname_change = timezone.now() - timedelta(days=8)
        self.profile.save() # Just to update the date in DB
        
        self.profile.display_name = "Second Nick"
        self.profile.full_clean() # Should not raise
        self.profile.save()
        self.assertEqual(self.profile.nickname_change_count, 2)

    def test_nickname_monthly_limit(self):
        # First change
        self.profile.display_name = "First Nick"
        self.profile.save()
        
        # Second change after 8 days
        self.profile.last_nickname_change = timezone.now() - timedelta(days=8)
        self.profile.nickname_change_count = 1
        self.profile.save()
        
        self.profile.display_name = "Second Nick"
        self.profile.save()
        self.assertEqual(self.profile.nickname_change_count, 2)

        # Third change after another 8 days in the same month
        self.profile.last_nickname_change = timezone.now() - timedelta(days=8)
        self.profile.save() # Still same month

        self.profile.display_name = "Third Nick"
        with self.assertRaises(ValidationError) as cm:
            self.profile.full_clean()
        self.assertIn("twice this month", str(cm.exception))

    def test_nickname_monthly_reset(self):
        # Two changes last month
        last_month = timezone.now() - timedelta(days=35)
        self.profile.last_nickname_change = last_month
        self.profile.nickname_change_count = 2
        self.profile.save()

        # Try to change now (new month)
        self.profile.display_name = "New Month Nick"
        self.profile.full_clean() # Should pass
        self.profile.save()
        self.assertEqual(self.profile.nickname_change_count, 1)
