import redis
import json
import logging
from config.settings import settings

# Configure logging
logging.basicConfig(
    filename='logs/pipeline.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)


class StateManager:
    def __init__(self):
        # Establish connection to Redis
        self.r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)

        # Redis Keys Definitions

        # Input Queue (Raw events from ATOMIC to be generated)
        self.QUEUE_KEY = "forensic:queue"

        # Intermediate Queue (Generated data waiting for judgment)
        self.TO_JUDGE_KEY = "forensic:to_judge_queue"

        # Output Buffer (Approved data waiting to be written to CSV)
        self.RESULTS_KEY = "forensic:results_buffer"

        # Sets for deduplication and state tracking
        self.PROCESSED_KEY = "forensic:processed"  # Events fully completed and saved
        self.GENERATED_SET = "forensic:generated_set"  # Events currently in judgment phase (to avoid re-generation)
        self.FAILED_KEY = "forensic:failed"  # Events that failed generation or judgment

    def populate_queue(self, events: list):
        """
        Loads events into the Redis Input Queue if they haven't been processed yet.
        Checks both the processed set and the currently-generating set to avoid duplicates.
        """
        pipeline = self.r.pipeline()
        count = 0
        for event in events:
            # Check if already processed OR currently waiting for judgment
            if not self.r.sismember(self.PROCESSED_KEY, event) and \
                    not self.r.sismember(self.GENERATED_SET, event):
                self.r.lpush(self.QUEUE_KEY, event)
                count += 1
        pipeline.execute()
        print(f"Queued {count} new events for generation.")

    # GENERATOR SIDE METHODS

    def get_generation_batch(self, size=1):
        """
        Retrieves a batch of raw events from the input queue for the generators.
        """
        items = []
        for _ in range(size):
            item = self.r.rpop(self.QUEUE_KEY)
            if item:
                items.append(item.decode('utf-8'))
            else:
                break
        return items

    def push_to_judge(self, event, data):
        """
        Called when a Generator finishes. Pushes the result to the Judgment Queue.
        """
        # Mark as generated to prevent re-queueing if the script restarts
        self.r.sadd(self.GENERATED_SET, event)

        # Create a package containing the original event and the generated JSON data
        package = json.dumps({"event": event, "data": data})
        self.r.lpush(self.TO_JUDGE_KEY, package)
        logging.info(f"GENERATED: {event[:30]}... -> Pushed to Judgment Queue")

    # JUDGE SIDE METHODS

    def get_judgment_batch(self, size=1):
        """
        Retrieves a batch of generated items (event + json) to be judged.
        """
        items = []
        for _ in range(size):
            item = self.r.rpop(self.TO_JUDGE_KEY)
            if item:
                items.append(json.loads(item))
            else:
                break
        return items

    def mark_final_success(self, event, data):
        """
        Called when the Judge approves content. Saves to the final result buffer.
        """
        # Mark as fully processed
        self.r.sadd(self.PROCESSED_KEY, event)

        # Push to the buffer for the CSV Writer
        self.r.rpush(self.RESULTS_KEY, json.dumps(data))
        logging.info(f"APPROVED: {event[:30]}... -> Saved to Results")

    def mark_failed(self, event, error):
        """
        Marks an event as failed (either generation error or judgment rejection).
        """
        self.r.sadd(self.FAILED_KEY, event)
        logging.error(f"FAIL: {event[:30]}... -> {error}")