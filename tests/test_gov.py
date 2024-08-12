import unittest
from contracting.stdlib.bridge.time import Datetime
from contracting.client import ContractingClient


class TestMembers(unittest.TestCase):
    def setUp(self):
        # Called before every test, bootstraps the environment.
        self.client = ContractingClient()
        self.client.flush()

        with open("currency.py") as f:
            code = f.read()
            self.client.submit(code, name="currency", constructor_args={"vk": "sys"})

        self.currency = self.client.get_contract("currency")
        
        RULES = {
            "v_max": 2,
            "v_lock": 100,
            "v_min_commission": 5,
            "fee_dist": [0.4, 0.3, 0.1, 0.2],
            "unbonding_period": 7,
            "epoch_length": 8,
        }

        with open("gov.py") as f:
            code = f.read()
            self.client.submit(code, name="gov", constructor_args={"genesis_nodes": ["node1", "node2"], "rules": RULES})
            
        self.gov = self.client.get_contract("gov")

    def tearDown(self):
        # Called after every test, ensures each test starts with a clean slate and is isolated from others
        self.client.flush()



    def test_constructor_defaults(self):
        with open("gov.py") as f:
            code = f.read()
            self.client.submit(code, name="gov_defaults", constructor_args={"genesis_nodes": ["node1", "node2"]})
            
        self.gov_defaults = self.client.get_contract("gov_defaults")
        
        # Check initial values set by constructor
        self.assertEqual(self.gov_defaults.Rules["v_max"], 0)
        self.assertEqual(self.gov_defaults.Rules["v_lock"], 0)
        self.assertEqual(self.gov_defaults.Rules["v_min_commission"], 0)
        self.assertEqual(self.gov_defaults.Rules["unbonding_period"], 0)
        self.assertEqual(self.gov_defaults.Rules["fee_dist"], [0, 0, 0, 0])
        self.assertEqual(self.gov_defaults.Rules["epoch_length"], 0)

    
    def test_constructor_variable(self):
        
        self.assertEqual(self.gov.Rules["v_max"], 2)
        self.assertEqual(self.gov.Rules["v_lock"], 100)
        self.assertEqual(self.gov.Rules["v_min_commission"], 5)
        self.assertEqual(self.gov.Rules["unbonding_period"], 7)
        self.assertEqual(self.gov.Rules["epoch_length"], 8)
        self.assertEqual(self.gov.Rules["fee_dist"], [0.4, 0.3, 0.1, 0.2])

        

    # def test_custom_constructor_args(self):
    #     genesis_nodes = ["node1", "node2"]
    #     rules = {
    #         "v_max": 10,
    #         "v_lock": 100.0,
    #         "v_min_commission": 0.05,
    #         "join_fee": 50.0,
    #         "unbonding_period": 7,
    #         "epoch_length": 24,
    #     }

        # env = {"now": Datetime(year=2021, month=1, day=1, hour=0)}
        # self.gov.seed(genesis_nodes=genesis_nodes, rules=rules, environment=env, signer='foundation')

        # # Check if rules are set correctly
        # self.assertEqual(self.gov.get_variable('Rules', 'v_max'), 10)
        # self.assertEqual(self.gov.get_variable('Rules', 'v_lock'), 100.0)
        # self.assertEqual(self.gov.get_variable('Rules', 'v_min_commission'), 0.05)
        # self.assertEqual(self.gov.get_variable('Rules', 'join_fee'), 50.0)
        # self.assertEqual(self.gov.get_variable('Rules', 'unbonding_period'), 7)
        # self.assertEqual(self.gov.get_variable('Rules', 'epoch_length'), 24)

    # def test_initial_balance(self):
    #     # Check initial balance set by constructor
    #     sys_balance = self.currency.balances["sys"]
    #     self.assertEqual(sys_balance, 1_000_000)

    # def test_transfer(self):
    #     # Setup
    #     self.currency.transfer(amount=100, to="bob", signer="sys")
    #     self.assertEqual(self.currency.balances["bob"], 100)
    #     self.assertEqual(self.currency.balances["sys"], 999_900)

    # def test_change_metadata(self):
    #     # Only the operator should be able to change metadata
    #     with self.assertRaises(Exception):
    #         self.currency.change_metadata(
    #             key="token_name", value="NEW TOKEN", signer="bob"
    #         )
    #     # Operator changes metadata
    #     self.currency.change_metadata(key="token_name", value="NEW TOKEN", signer="sys")
    #     new_name = self.currency.metadata["token_name"]
    #     self.assertEqual(new_name, "NEW TOKEN")

    # def test_approve_and_allowance(self):
    #     # Test approve
    #     self.currency.approve(amount=500, to="eve", signer="sys")
    #     # Test allowance
    #     allowance = self.currency.balances["sys", "eve"]
    #     self.assertEqual(allowance, 500)

    # def test_transfer_from_without_approval(self):
    #     # Attempt to transfer without approval should fail
    #     with self.assertRaises(Exception):
    #         self.currency.transfer_from(
    #             amount=100, to="bob", main_account="sys", signer="bob"
    #         )

    # def test_transfer_from_with_approval(self):
    #     # Setup - approve first
    #     self.currency.approve(amount=200, to="bob", signer="sys")
    #     # Now transfer
    #     self.currency.transfer_from(
    #         amount=100, to="bob", main_account="sys", signer="bob"
    #     )
    #     self.assertEqual(self.currency.balances["bob"], 100)
    #     self.assertEqual(self.currency.balances["sys"], 999_900)
    #     remaining_allowance = self.currency.balances["sys", "bob"]
    #     self.assertEqual(remaining_allowance, 100)


if __name__ == "__main__":
    unittest.main()
