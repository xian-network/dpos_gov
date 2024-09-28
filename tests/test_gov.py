import unittest
from contracting.stdlib.bridge.time import Datetime, Timedelta
from contracting.client import ContractingClient
from parameterized import parameterized

from gov_utils import calculate_reward_percentage, get_validators

# from gov_utils import get_validators


class TestGovernance(unittest.TestCase):

    NODES = [
        "node1",
        "node2",
        "node3",
        "node4",
        "node5",
        "node6",
        "node7",
        "node8",
        "node9",
        "node10",
    ]

    RULES = {
        "v_max": 2,
        "v_lock": 100,
        "v_min_commission": 5,
        "fee_dist": [0.4, 0.3, 0.1, 0.2],
        "unbonding_period": 7,
        "epoch_length": 8,
        "min_vote_turnout": 0.5,
        "min_vote_ratio": 0.7,
    }

    GENESIS_NODES = ["node1", "node2"]

    def setUp(self):
        # Called before every test, bootstraps the environment.
        self.client = ContractingClient()
        self.client.flush()

        gov_contract_name = "gov"
        currency_contract_name = "currency"

        self.setup_currency_contract(currency_contract_name, gov_contract_name)
        self.currency = self.client.get_contract("currency")

        self.setup_gov_contract(gov_contract_name, self.RULES, self.GENESIS_NODES)
        self.gov = self.client.get_contract(gov_contract_name)

        self.setup_nodes_currency(self.NODES, gov_contract_name)

    def tearDown(self):
        # Called after every test, ensures each test starts with a clean slate and is isolated from others
        self.client.flush()

    def setup_nodes_currency(
        self, nodes, gov_contract_name, currency_contract_name="currency"
    ):
        currency_contract = self.client.get_contract(currency_contract_name)
        for node in nodes:
            currency_contract.transfer(amount=10000, to=node, signer="sys")
            currency_contract.approve(amount=10000, to=gov_contract_name, signer=node)

    def setup_currency_contract(self, contract_name, gov_contract_name):
        with open("currency.py") as f:
            code = f.read()
            self.client.submit(
                code,
                contract_name,
                constructor_args={"vk": "sys", "gov_contract": gov_contract_name},
            )

    def setup_gov_contract(self, contract_name, rules, genesis_nodes):
        with open("gov.py") as f:
            code = f.read()
            self.client.submit(
                code,
                name=contract_name,
                constructor_args={"genesis_nodes": genesis_nodes, "rules": rules},
            )

    def test_constructor_defaults(self):
        with open("gov.py") as f:
            code = f.read()
            self.client.submit(
                code,
                name="gov_defaults",
                constructor_args={"genesis_nodes": ["node1", "node2"]},
            )

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

    def test_initial_members(self):
        self.assertEqual(self.gov.Validators["node1", "active"], True)
        self.assertEqual(self.gov.Validators["node2", "active"], True)
        self.assertEqual(self.gov.Validators["node1", "locked"], 100)
        self.assertEqual(self.gov.Validators["node2", "locked"], 100)
        self.assertEqual(self.gov.Validators["node1", "unbonding"], None)
        self.assertEqual(self.gov.Validators["node2", "unbonding"], None)
        self.assertEqual(self.gov.Validators["node1", "power"], 100)
        self.assertEqual(self.gov.Validators["node2", "power"], 100)
        self.assertEqual(self.gov.Validators["node1", "commission"], 5)
        self.assertEqual(self.gov.Validators["node2", "commission"], 5)
        self.assertEqual(self.gov.Validators["node1", "epoch_joined"], 0)
        self.assertEqual(self.gov.Validators["node2", "epoch_joined"], 0)
        self.assertEqual(self.gov.Validators["node1", "epoch_collected"], None)
        self.assertEqual(self.gov.Validators["node2", "epoch_collected"], None)
        self.assertEqual(self.gov.Validators["node1", "is_genesis_node"], True)
        self.assertEqual(self.gov.Validators["node2", "is_genesis_node"], True)

    def test_join_commission_too_low(self):
        self.assertRaises(Exception, self.gov.join, commission=4, signer="node3")

    def test_announce_validator_leave(self):
        DATE = Datetime(year=2021, month=1, day=1, hour=0)
        expected_unbonding = Datetime(year=2021, month=1, day=8, hour=0)
        self.gov.announce_validator_leave(signer="node1", environment={"now": DATE})
        self.assertEqual(self.gov.Validators["node1", "unbonding"], expected_unbonding)

    def test_announce_validator_leave_not_member(self):
        self.assertRaises(Exception, self.gov.announce_validator_leave, signer="node3")

    def test_announce_validator_leave_already_unbonding(self):
        self.gov.announce_validator_leave(signer="node1")
        self.assertRaises(Exception, self.gov.announce_validator_leave, signer="node1")

    def test_cancel_validator_leave(self):
        self.gov.announce_validator_leave(signer="node1")
        self.gov.cancel_validator_leave(signer="node1")
        self.assertEqual(self.gov.Validators["node1", "unbonding"], None)

    def test_cancel_validator_leave_not_member(self):
        with self.assertRaises(Exception) as context:
            self.gov.cancel_validator_leave(signer="node3")
        self.assertEqual(str(context.exception), "Not an active validator")

    def assert_cancel_validator_leave_already_unbonding(self):
        self.gov.announce_validator_leave(signer="node1")
        self.gov.cancel_validator_leave(signer="node1")
        self.assertRaises(Exception, self.gov.cancel_validator_leave, signer="node1")

    def test_validator_leave_not_announced(self):
        self.assertRaises(Exception, self.gov.validator_leave, signer="node2")

    def test_join(self):
        initial_balance = self.currency.balances["node3"]

        self.gov.join(commission=5, signer="node3")
        self.assertEqual(self.gov.Validators["node3", "active"], True)
        self.assertEqual(self.gov.Validators["node3", "locked"], 100)
        self.assertEqual(self.gov.Validators["node3", "unbonding"], None)
        self.assertEqual(self.gov.Validators["node3", "power"], 100)
        self.assertEqual(self.gov.Validators["node3", "commission"], 5)
        self.assertEqual(self.gov.Validators["node3", "epoch_joined"], 1)
        self.assertEqual(self.gov.Validators["node3", "epoch_collected"], None)
        self.assertEqual(self.gov.Validators["node3", "is_genesis_node"], None)
        self.assertEqual(self.currency.balances["node3"], initial_balance - 100)

    def test_join_already_member(self):
        self.assertRaises(Exception, self.gov.join, commission=5, signer="node1")

    def test_initial_member_announce_and_leave(self):
        announce_leave_date = Datetime(year=2021, month=1, day=1, hour=0)
        leave_date = Datetime(year=2021, month=1, day=8, hour=1)
        initial_balance = self.currency.balances["node1"]
        self.gov.announce_validator_leave(
            signer="node1", environment={"now": announce_leave_date}
        )
        self.gov.validator_leave(signer="node1", environment={"now": leave_date})
        self.assertEqual(self.currency.balances["node1"], initial_balance)
        self.assertEqual(self.gov.Validators["node1"], None)
        self.assertEqual(self.gov.Validators["node1", "locked"], None)
        self.assertEqual(self.gov.Validators["node1", "unbonding"], None)
        self.assertEqual(self.gov.Validators["node1", "power"], 0)

    def test_initial_member_announce_and_leave_unbonding_not_over(self):
        announce_leave_date = Datetime(year=2021, month=1, day=1, hour=0)
        leave_date = Datetime(year=2021, month=1, day=7, hour=23)
        self.gov.announce_validator_leave(
            signer="node1", environment={"now": announce_leave_date}
        )
        self.assertRaises(
            Exception,
            self.gov.validator_leave,
            signer="node1",
            environment={"now": leave_date},
        )
        self.assertEqual(self.gov.Validators["node1", "active"], True)

    def test_delegate(self):
        self.gov.join(commission=5, signer="node3")
        self.gov.delegate(validator="node3", amount=100, signer="node4")
        self.assertEqual(self.gov.Validators["node3", "power"], 200)
        self.assertEqual(self.gov.Delegators["node4", "node3", "amount"], 100)
        self.assertEqual(self.gov.Delegators["node4", "node3", "unbonding"], None)
        self.assertEqual(self.gov.Delegators["node4", "node3", "epoch_joined"], 1)

    def test_delegate_not_validator(self):
        with self.assertRaises(Exception) as context:
            self.gov.delegate(validator="node3", amount=100, signer="node4")
        self.assertEqual(str(context.exception), "Validator is not registered")

    def test_delegate_not_enough_balance(self):
        with self.assertRaises(Exception) as context:
            self.gov.delegate(validator="node2", amount=100000, signer="node4")
        self.assertEqual(str(context.exception), "Insufficient funds")

    def test_delegate_not_enough_approval(self):
        self.currency.approve(amount=50, to="gov", signer="node3")
        with self.assertRaises(Exception) as context:
            self.gov.delegate(validator="node2", amount=100, signer="node3")
        self.assertEqual(str(context.exception), "Insufficient allowance")

    def test_delegate_while_unbonding(self):
        self.gov.delegate(validator="node2", amount=100, signer="node3")
        self.gov.announce_delegator_leave(validator="node2", signer="node3")
        with self.assertRaises(Exception) as context:
            self.gov.delegate(validator="node2", amount=100, signer="node3")
        self.assertEqual(
            str(context.exception),
            "This delegation is unbonding, please cancel the unbonding period first",
        )

    def test_announce_delegator_leave(self):
        JOIN_DATE = Datetime(year=2021, month=1, day=1, hour=0)
        self.gov.delegate(
            validator="node2",
            amount=100,
            signer="node3",
            environment={"now": JOIN_DATE},
        )
        self.gov.announce_delegator_leave(
            validator="node2", signer="node3", environment={"now": JOIN_DATE}
        )

        self.assertEqual(
            self.gov.Delegators["node3", "node2", "unbonding"],
            JOIN_DATE + Timedelta(days=7),
        )
        self.assertEqual(self.gov.Delegators["node3", "node2", "amount"], 100)
        self.assertEqual(self.gov.Delegators["node3", "node2", "epoch_joined"], 1)
        self.assertEqual(self.gov.Validators["node2", "power"], 100)

    def test_delegator_cancel_leave(self):
        self.gov.delegate(validator="node2", amount=100, signer="node3")
        self.gov.announce_delegator_leave(validator="node2", signer="node3")
        self.gov.cancel_delegator_leave(validator="node2", signer="node3")

        self.assertEqual(self.gov.Delegators["node3", "node2", "unbonding"], None)
        self.assertEqual(self.gov.Delegators["node3", "node2", "amount"], 100)
        self.assertEqual(self.gov.Delegators["node3", "node2", "epoch_joined"], 1)
        self.assertEqual(self.gov.Validators["node2", "power"], 200)

    def test_delegator_cancel_leave_not_announced(self):
        self.gov.delegate(validator="node2", amount=100, signer="node3")
        with self.assertRaises(Exception) as context:
            self.gov.cancel_delegator_leave(validator="node2", signer="node3")
        self.assertEqual(str(context.exception), "Not unbonding")

    def test_delegator_leave_not_announced(self):
        self.gov.delegate(validator="node2", amount=100, signer="node3")
        with self.assertRaises(Exception) as context:
            self.gov.delegator_leave(validator="node2", signer="node3")
        self.assertEqual(
            str(context.exception), "Not unbonding, call announce_delegator_leave first"
        )

    def test_delegator_leave_unbonding_period_not_over(self):
        JOIN_DATE = Datetime(year=2021, month=1, day=1, hour=0)
        self.gov.delegate(
            validator="node2",
            amount=100,
            signer="node3",
            environment={"now": JOIN_DATE},
        )
        self.gov.announce_delegator_leave(
            validator="node2", signer="node3", environment={"now": JOIN_DATE}
        )
        with self.assertRaises(Exception) as context:
            self.gov.delegator_leave(
                validator="node2",
                signer="node3",
                environment={"now": JOIN_DATE + Timedelta(days=6)},
            )
        self.assertEqual(str(context.exception), "Unbonding period not over")

    def test_delegator_leave(self):
        JOIN_DATE = Datetime(year=2021, month=1, day=1, hour=0)
        self.gov.delegate(
            validator="node2",
            amount=100,
            signer="node3",
            environment={"now": JOIN_DATE},
        )
        self.gov.announce_delegator_leave(
            validator="node2", signer="node3", environment={"now": JOIN_DATE}
        )
        self.gov.delegator_leave(
            validator="node2",
            signer="node3",
            environment={"now": JOIN_DATE + Timedelta(days=7)},
        )

        self.assertEqual(self.gov.Delegators["node3", "node2", "unbonding"], None)
        self.assertEqual(self.gov.Delegators["node3", "node2", "amount"], 0)
        self.assertEqual(self.gov.Delegators["node3", "node2", "epoch_joined"], 1)

    def test_delegator_leave_join_again(self):
        JOIN_DATE = Datetime(year=2021, month=1, day=1, hour=0)
        self.gov.delegate(
            validator="node2",
            amount=100,
            signer="node3",
            environment={"now": JOIN_DATE},
        )
        self.gov.announce_delegator_leave(
            validator="node2", signer="node3", environment={"now": JOIN_DATE}
        )
        self.gov.delegator_leave(
            validator="node2",
            signer="node3",
            environment={"now": JOIN_DATE + Timedelta(days=7)},
        )
        self.gov.Epoch_I.set(1)
        self.gov.delegate(
            validator="node2",
            amount=100,
            signer="node3",
            environment={"now": JOIN_DATE + Timedelta(days=7)},
        )

        self.assertEqual(self.gov.Delegators["node3", "node2", "unbonding"], None)
        self.assertEqual(self.gov.Delegators["node3", "node2", "amount"], 100)
        self.assertEqual(self.gov.Delegators["node3", "node2", "epoch_joined"], 2)

    @parameterized.expand(
        [ # (genesis, unbonding, inactive)
            (["node1", "node2"], ["node3", "node4", "node5"], ["node6", "node7", "node8"]),
            (["node1", "node2", "node3", "node4"], ["node5"], ["node6", "node7", "node8"]),
            (["node1", "node2", "node3", "node4"], ["node5", "node6"], ["node7", "node8"]),
            (["node1", "node2", "node3", "node4", "node5", "node6"], [], ["node7", "node8"]),
            (["node1", "node2", "node3", "node4", "node5", "node6", "node7", "node8"], [], []),
        ]
    )
    def test_get_validators(self, genesis_nodes, unbonding, inactive):
        JOIN_DATE = Datetime(year=2021, month=1, day=1, hour=0)
        LEAVE_DATE = Datetime(year=2021, month=1, day=8, hour=0)

        gov_contract_name = "gov_local"
        self.setup_gov_contract(gov_contract_name, self.RULES, genesis_nodes)

        gov = self.client.get_contract(gov_contract_name)
        self.setup_nodes_currency(self.NODES, gov_contract_name)

        for node in unbonding + inactive:
            gov.join(commission=5, signer=node, environment={"now": JOIN_DATE})
            gov.announce_validator_leave(signer=node, environment={"now": JOIN_DATE})

        for node in inactive:
            gov.validator_leave(signer=node, environment={"now": LEAVE_DATE})

        available_validators, inactive_validators_accounts, unbonding_validator_accounts = get_validators(self.client.raw_driver, gov_contract_name)
        for v in available_validators:
            assert v["account"] in genesis_nodes
        for v in unbonding_validator_accounts:
            assert v["account"] in unbonding
        for v in inactive_validators_accounts:
            assert v["account"] in inactive

    @parameterized.expand(
        [ # (genesis, joined_later, inactive)
            (["node1", "node2"], ["node3", "node4", "node5"], ["node6", "node7", "node8"]),
            (["node1", "node2", "node3", "node4"], ["node5"], ["node6", "node7", "node8"]),
            (["node1", "node2", "node3", "node4"], ["node5", "node6"], ["node7", "node8"]),
            (["node1", "node2", "node3", "node4", "node5", "node6"], [], ["node7", "node8"]),
            (["node1", "node2", "node3", "node4", "node5", "node6", "node7", "node8"], [], []),
        ]
    )
    def test_get_validators_joined_later(self, genesis_nodes, joined_later, inactive):
        JOIN_DATE = Datetime(year=2021, month=1, day=1, hour=0)
        LEAVE_DATE = Datetime(year=2021, month=1, day=8, hour=0)

        gov_contract_name = "gov_local"
        self.setup_gov_contract(gov_contract_name, self.RULES, genesis_nodes)

        gov = self.client.get_contract(gov_contract_name)
        self.setup_nodes_currency(self.NODES, gov_contract_name)

        for node in joined_later:
            gov.join(commission=5, signer=node, environment={"now": JOIN_DATE})

        for node in inactive:
            gov.join(commission=5, signer=node, environment={"now": JOIN_DATE})
            gov.announce_validator_leave(signer=node, environment={"now": JOIN_DATE})
            gov.validator_leave(signer=node, environment={"now": LEAVE_DATE})

        available_validators, inactive_validators_accounts, unbonding_validator_accounts = get_validators(self.client.raw_driver, gov_contract_name)

        for v in available_validators:
            assert v["account"] in genesis_nodes + joined_later
        for v in inactive_validators_accounts:
            assert v["account"] in inactive

    @parameterized.expand(
        [ # (genesis, joined_later, leave_rejoin, leave_rejoin_announce_leave)
            (["node1", "node2"], ["node3", "node4", "node5"], ["node6", "node7", "node8"], ["node9", "node10"]),
            (["node1", "node2", "node3", "node4"], ["node5"], ["node6", "node7", "node8", "node9"], ["node10"]),
            (["node1", "node2", "node3", "node4"], ["node5", "node6"], ["node7", "node8"], ["node9", "node10"]),
            (["node1", "node2", "node3", "node4", "node5", "node6"], [], ["node7", "node8"], ["node9", "node10"]),
            (["node1", "node2", "node3", "node4", "node5", "node6", "node7", "node8"], [], [], ["node9", "node10"]),
        ]
    )
    def test_get_validators_leave_rejoin(self, genesis_nodes, joined_later, leave_rejoin, leave_rejoin_announce_leave):
        JOIN_DATE = Datetime(year=2021, month=1, day=1, hour=0)
        LEAVE_DATE = Datetime(year=2021, month=1, day=8, hour=0)

        gov_contract_name = "gov_local"
        self.setup_gov_contract(gov_contract_name, self.RULES, genesis_nodes)

        gov = self.client.get_contract(gov_contract_name)
        self.setup_nodes_currency(self.NODES, gov_contract_name)

        for node in joined_later:
            gov.join(commission=5, signer=node, environment={"now": JOIN_DATE})

        for node in leave_rejoin + leave_rejoin_announce_leave:
            gov.join(commission=5, signer=node, environment={"now": JOIN_DATE})
            gov.announce_validator_leave(signer=node, environment={"now": JOIN_DATE})
            gov.validator_leave(signer=node, environment={"now": LEAVE_DATE})
            gov.join(commission=5, signer=node, environment={"now": LEAVE_DATE})

        for node in leave_rejoin_announce_leave:
            leave_rejoin_leaveannounce__date = LEAVE_DATE + Timedelta(days=1)
            gov.announce_validator_leave(signer=node, environment={"now": leave_rejoin_leaveannounce__date})

        available_validators, inactive_validators_accounts, unbonding_validator_accounts = get_validators(self.client.raw_driver, gov_contract_name)

        for v in available_validators:
            assert v["account"] in genesis_nodes + joined_later + leave_rejoin
        for v in unbonding_validator_accounts:
            assert v["account"] in leave_rejoin_announce_leave

    # @parameterized.expand(
    #     [
    #         # (0.1, 18.8),
    #         # (0.2, 18.8),
    #         # (0.3, 10),
    #         # (0.4, 9.88),
    #         # (0.5, 8.18),
    #         # (0.6, 5.12),
    #         # (0.7, 5.12),
    #         # (0.73, 5.12),
    #         # (0.74, 5.12),
    #         # (0.749, 5.12),
    #         (0.8, 5.12),
    #         (0.9, 5.12),
    #         (1, 5.12),
    #     ]
    # )
    # def test_calculate_reward_percentage(self, staked, expected_reward):
    #     # Example usage
    #     staked_target = 0.75
    #     reward_min = 0.05
    #     reward_max = 0.35
    #     reward_target = 0.05

    #     reward_percentage = calculate_reward_percentage(
    #         staked,
    #         staked_target,
    #         reward_target,
    #         reward_max,
    #         reward_min,
    #     )
    #     self.assertAlmostEqual(
    #         reward_percentage,
    #         expected_reward,
    #         places=2,
    #         msg=f"Staked Amount: {staked}, Expected Reward Percentage: {expected_reward}%, Got: {reward_percentage:.2f}%",
    #     )


if __name__ == "__main__":
    unittest.main()
