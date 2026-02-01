from tests.test_api_contract import test_create_job_tmx010, test_idempotency_tmx011

try:
    print("Running test_create_job_tmx010...")
    test_create_job_tmx010()
    print("PASS test_create_job_tmx010")
    
    print("Running test_idempotency_tmx011...")
    test_idempotency_tmx011()
    print("PASS test_idempotency_tmx011")
    
except Exception as e:
    import traceback
    traceback.print_exc()
