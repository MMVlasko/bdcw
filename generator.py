import requests
import json
import time
import random
from datetime import datetime, timedelta
from decimal import Decimal
from faker import Faker
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestDataGenerator:
    def __init__(self, base_url: str = "http://127.0.0.1:8080/api", token: str = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.fake = Faker('ru_RU')
        self.session = requests.Session()

        if token:
            self.session.headers.update({
                'Authorization': token,
                'Content-Type': 'application/json'
            })

        self.created_users = []
        self.created_categories = []
        self.created_goals = []
        self.created_habits = []
        self.created_challenges = []

    def make_request(self, method, endpoint, data=None):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=data)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()

            if response.status_code != 204:
                return response.json()
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {method} {url} - {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def batch_import(self, endpoint, data_key, items):
        batch_size = 100
        all_created_ids = []

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            payload = {
                data_key: batch,
                "batch_size": batch_size
            }

            logger.info(f"Importing batch {i // batch_size + 1}/{(len(items) - 1) // batch_size + 1} to {endpoint}")

            result = self.make_request('POST', endpoint, payload)

            if result and 'created_ids' in result:
                created_ids = result['created_ids']
                all_created_ids.extend(created_ids)
                logger.info(f"Created {len(created_ids)} items in this batch")
            else:
                logger.error(f"Failed to import batch to {endpoint}")
                logger.error(f"Response: {result}")

            time.sleep(0.1)

        return all_created_ids

    def generate_users(self, count=500):
        logger.info(f"Generating {count} users...")

        users = []
        used_usernames = set()

        while len(users) < count:
            username_base = self.fake.user_name()
            username = f"{username_base}{random.randint(1000, 9999)}"

            if username in used_usernames:
                continue

            password = self.fake.password(length=12)

            user = {
                "username": username,
                "password": password,
                "confirm_password": password,
                "first_name": self.fake.first_name(),
                "last_name": self.fake.last_name(),
                "role": random.choice(["user", "manager", "admin"]),
                "is_active": random.random() > 0.1,
                "is_public": random.random() > 0.3,
                "description": self.fake.text(max_nb_chars=100) if random.random() > 0.5 else None
            }
            users.append(user)
            used_usernames.add(username)

        user_ids = self.batch_import("users/batch-import/", "users", users)

        self.created_users = user_ids
        logger.info(f"Successfully generated {len(user_ids)} users")
        return user_ids

    def generate_categories(self, count=30):
        logger.info(f"Generating {count} categories...")

        categories = []
        category_names = set()

        themes = ["Спорт", "Здоровье", "Образование", "Карьера", "Финансы", "Творчество",
                  "Отношения", "Психология", "Путешествия", "Языки", "Музыка", "Искусство",
                  "Программирование", "Кулинария", "Саморазвитие", "Медитация", "Чтение",
                  "Писательство", "Бизнес", "Инвестиции", "Фотография", "Дизайн", "Маркетинг",
                  "Наука", "История", "Философия", "Экология", "Волонтерство", "Ремесло", "Технологии"]

        while len(categories) < count:
            if len(categories) < len(themes):
                theme = themes[len(categories)]
                name = f"{theme}: {self.fake.word().capitalize()}"
            else:
                name = f"{self.fake.word().capitalize()} {self.fake.word().capitalize()}"

            if name not in category_names:
                category = {
                    "name": name,
                    "description": self.fake.text(max_nb_chars=200) if random.random() > 0.3 else None
                }
                categories.append(category)
                category_names.add(name)

        category_ids = self.batch_import("categories/batch-import/", "categories", categories)

        if len(category_ids) < count:
            logger.warning(f"Requested {count} categories, but only {len(category_ids)} were created")

        self.created_categories = category_ids
        logger.info(f"Generated {len(category_ids)} categories")
        return category_ids

    def generate_goals(self, count=500):
        if not self.created_users or not self.created_categories:
            raise ValueError("Need users and categories first")

        logger.info(f"Generating {count} goals...")

        goals = []
        for i in range(count):
            user_id = random.choice(self.created_users)
            category_id = random.choice(self.created_categories)

            start_date = self.fake.date_this_year(before_today=True, after_today=False)
            deadline = start_date + timedelta(days=random.randint(30, 365))

            goal = {
                "user_id": user_id,
                "title": self.fake.sentence(nb_words=random.randint(3, 8))[:-1],
                "description": self.fake.text(max_nb_chars=200) if random.random() > 0.4 else None,
                "target_value": round(random.uniform(100, 100000), 2),
                "deadline": deadline.strftime("%Y-%m-%d"),
                "category_id": category_id,
                "is_completed": random.random() > 0.8,
                "is_public": random.random() > 0.3
            }
            goals.append(goal)

        goal_ids = self.batch_import("goals/batch-import/", "goals", goals)

        if len(goal_ids) < count:
            logger.warning(f"Requested {count} goals, but only {len(goal_ids)} were created")

        self.created_goals = goal_ids
        logger.info(f"Generated {len(goal_ids)} goals")
        return goal_ids

    def generate_habits(self, count=500):
        if not self.created_users or not self.created_categories:
            raise ValueError("Need users and categories first")

        logger.info(f"Generating {count} habits...")

        habits = []
        for i in range(count):
            user_id = random.choice(self.created_users)
            category_id = random.choice(self.created_categories)

            habit = {
                "user_id": user_id,
                "title": self.fake.sentence(nb_words=random.randint(2, 6))[:-1],
                "description": self.fake.text(max_nb_chars=150) if random.random() > 0.4 else None,
                "frequency_type": random.randint(1, 4),
                "frequency_value": random.randint(1, 7),
                "category_id": category_id,
                "is_active": random.random() > 0.2,
                "is_public": random.random() > 0.3
            }
            habits.append(habit)

        habit_ids = self.batch_import("habits/batch-import/", "habits", habits)

        if len(habit_ids) < count:
            logger.warning(f"Requested {count} habits, but only {len(habit_ids)} were created")

        self.created_habits = habit_ids
        logger.info(f"Generated {len(habit_ids)} habits")
        return habit_ids

    def generate_goal_progresses(self, count=5000):
        if not self.created_goals:
            raise ValueError("Need goals first")

        logger.info(f"Generating {count} goal progresses...")

        progresses = []

        goals_count = len(self.created_goals)
        progresses_per_goal = max(1, count // goals_count)

        logger.info(f"Generating approximately {progresses_per_goal} progresses per goal")

        for goal_id in self.created_goals:
            current_value = 0
            start_date = self.fake.date_this_year(before_today=True, after_today=False)

            for day_offset in range(progresses_per_goal):
                progress_date = start_date + timedelta(days=day_offset * random.randint(7, 30))

                current_value += round(random.uniform(10, 1000), 2)

                progress = {
                    "goal_id": goal_id,
                    "progress_date": progress_date.strftime("%Y-%m-%d"),
                    "current_value": current_value,
                    "notes": self.fake.text(max_nb_chars=100) if random.random() > 0.5 else None
                }
                progresses.append(progress)

                if len(progresses) >= count:
                    break

            if len(progresses) >= count:
                break

        while len(progresses) < count:
            goal_id = random.choice(self.created_goals)
            progress_date = self.fake.date_this_year(before_today=True, after_today=False)

            progress = {
                "goal_id": goal_id,
                "progress_date": progress_date.strftime("%Y-%m-%d"),
                "current_value": round(random.uniform(10, 5000), 2),
                "notes": self.fake.text(max_nb_chars=100) if random.random() > 0.5 else None
            }
            progresses.append(progress)

        logger.info(f"Created {len(progresses)} progress records for import")

        progress_ids = self.batch_import("goals/progress/batch-import/", "goal_progresses", progresses)

        logger.info(f"Generated {len(progress_ids)} goal progresses")
        return progress_ids

    def generate_habit_logs(self, count=5000):
        if not self.created_habits:
            raise ValueError("Need habits first")

        logger.info(f"Generating {count} habit logs...")

        logs = []

        habits_count = len(self.created_habits)
        logs_per_habit = max(1, count // habits_count)

        logger.info(f"Generating approximately {logs_per_habit} logs per habit")

        for habit_id in self.created_habits:
            start_date = self.fake.date_this_year(before_today=True, after_today=False)

            for day_offset in range(logs_per_habit):
                log_date = start_date + timedelta(days=day_offset)

                log = {
                    "habit_id": habit_id,
                    "log_date": log_date.strftime("%Y-%m-%d"),
                    "status": random.choice(["completed", "skipped", "failed"]),
                    "notes": self.fake.text(max_nb_chars=80) if random.random() > 0.6 else None
                }
                logs.append(log)

                if len(logs) >= count:
                    break

            if len(logs) >= count:
                break

        while len(logs) < count:
            habit_id = random.choice(self.created_habits)
            log_date = self.fake.date_this_year(before_today=True, after_today=False)

            log = {
                "habit_id": habit_id,
                "log_date": log_date.strftime("%Y-%m-%d"),
                "status": random.choice(["completed", "skipped", "failed"]),
                "notes": self.fake.text(max_nb_chars=80) if random.random() > 0.6 else None
            }
            logs.append(log)

        logger.info(f"Created {len(logs)} habit log records for import")

        log_ids = self.batch_import("habits/log/batch-import/", "habit_logs", logs)

        logger.info(f"Generated {len(log_ids)} habit logs")
        return log_ids

    def generate_challenges(self, count=500):
        if not self.created_categories or not self.created_goals:
            raise ValueError("Need categories and goals first")

        logger.info(f"Generating {count} challenges...")

        challenges = []
        for i in range(count):
            start_date = self.fake.date_this_year(after_today=True)
            duration_days = random.choice([7, 14, 30, 60, 90])
            end_date = start_date + timedelta(days=duration_days)

            num_categories = min(random.randint(5, 10), len(self.created_categories))
            selected_categories = random.sample(self.created_categories, num_categories)

            num_goals = min(random.randint(5, 10), len(self.created_goals))
            selected_goals = random.sample(self.created_goals, num_goals)

            challenge = {
                "name": f"Челлендж: {self.fake.sentence(nb_words=random.randint(3, 6))[:-1]}",
                "description": self.fake.text(max_nb_chars=300) if random.random() > 0.3 else None,
                "target_value": round(random.uniform(1000, 50000), 2),
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "is_active": random.random() > 0.1,
                "category_ids": selected_categories,
                "goal_ids": selected_goals
            }
            challenges.append(challenge)

        challenge_ids = self.batch_import("challenges/batch-import/", "challenges", challenges)

        if len(challenge_ids) < count:
            logger.warning(f"Requested {count} challenges, but only {len(challenge_ids)} were created")

        self.created_challenges = challenge_ids
        logger.info(f"Generated {len(challenge_ids)} challenges")
        return challenge_ids

    def generate_subscriptions(self, count: int = 500) -> List[Dict]:
        if not self.created_users or len(self.created_users) < 2:
            raise ValueError("Need at least 2 users first")

        logger.info(f"Generating {count} subscriptions...")

        subscriptions = []
        subscription_pairs = set()
        max_possible = len(self.created_users) * (len(self.created_users) - 1)

        if count > max_possible:
            logger.warning(f"Requested {count} subscriptions, but maximum possible is {max_possible}")
            count = max_possible

        while len(subscriptions) < count:
            subscriber_id = random.choice(self.created_users)
            subscribing_id = random.choice(self.created_users)

            if subscriber_id == subscribing_id:
                continue

            pair = (subscriber_id, subscribing_id)
            if pair in subscription_pairs:
                continue

            subscription = {
                "subscriber_id": subscriber_id,
                "subscribing_id": subscribing_id
            }
            subscriptions.append(subscription)
            subscription_pairs.add(pair)

            if random.random() < 0.3 and len(subscriptions) < count:
                reverse_pair = (subscribing_id, subscriber_id)
                if reverse_pair not in subscription_pairs:
                    reverse_subscription = {
                        "subscriber_id": subscribing_id,
                        "subscribing_id": subscriber_id
                    }
                    subscriptions.append(reverse_subscription)
                    subscription_pairs.add(reverse_pair)

        subscription_ids = self.batch_import("subscriptions/batch-import/", "subscriptions", subscriptions)

        logger.info(f"Generated {len(subscription_ids)} subscriptions")
        return subscription_ids

    def generate_all_data(self):
        logger.info("Starting data generation...")
        logger.info(f"Using base URL: {self.base_url}")

        start_time = time.time()

        try:
            self.generate_users()

            self.generate_categories()

            self.generate_goals()

            self.generate_habits()

            self.generate_goal_progresses()

            self.generate_habit_logs()

            self.generate_challenges()

            self.generate_subscriptions()

            elapsed_time = time.time() - start_time
            logger.info(f"Data generation completed in {elapsed_time:.2f} seconds")

        except Exception as e:
            logger.error(f"Error during data generation: {e}")
            raise


def test_connection(base_url, token=None):
    print(f"Testing connection to {base_url}...")

    test_endpoints = [
        "categories/batch-import/",
        "users/batch-import/",
        "goals/batch-import/"
    ]

    headers = {}
    if token:
        headers['Authorization'] = token

    for endpoint in test_endpoints:
        url = f"{base_url.rstrip('/')}/{endpoint}"
        try:
            response = requests.post(url, json={}, headers=headers, timeout=5)
            if response.status_code in [400, 401, 403]:
                print(f"{endpoint}: Server is responding (status {response.status_code})")
                return True
            elif response.status_code == 405:
                print(f"{endpoint}: Server is responding (status {response.status_code})")
                return True
        except requests.exceptions.ConnectionError:
            print(f"{endpoint}: Connection failed")
            return False
        except Exception as e:
            print(f"{endpoint}: {e}")

    return True


def main():
    BASE_URL = "http://127.0.0.1:8080/api"
    AUTH_TOKEN = "767723a59106846be347cfdcda32d5bfc72d849dea736089f9c8dacdbd561630"

    if not test_connection(BASE_URL, AUTH_TOKEN):
        print("\nCannot connect to server.")
        print("Please make sure:")
        print("1. Django server is running: python manage.py runserver 8080")
        print("2. Server is accessible at: http://127.0.0.1:8080")
        print("3. Port 8080 is not blocked by firewall")
        return

    print("\nConnection successful!")

    generator = TestDataGenerator(base_url=BASE_URL, token=AUTH_TOKEN)

    try:
        generator.generate_all_data()
        print("\n Data generation completed successfully!")
        print("\n" + "=" * 60)
        print("FINAL SUMMARY:")
        print("=" * 60)
        print(f"Users created: {len(generator.created_users)}")
        print(f"Categories created: {len(generator.created_categories)}")
        print(f"Goals created: {len(generator.created_goals)}")
        print(f"Habits created: {len(generator.created_habits)}")
        print(f"Challenges created: {len(generator.created_challenges)}")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\nData generation interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        print("\nPossible issues:")
        print("1. Invalid authentication token")
        print("2. Insufficient permissions (need admin)")
        print("3. Server error")


if __name__ == "__main__":
    try:
        import requests
        import faker
        from collections import defaultdict
    except ImportError:
        print("Missing dependencies. Please install:")
        print("pip install requests faker")
        exit(1)

    main()
