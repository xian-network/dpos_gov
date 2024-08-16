# import dao
# import rewards
# import stamp_cost
import currency

# appease the linter
# import export
# import construct
# import ctx
# import Hash
# import now
# import datetime

Actions = Hash()  # Actions, using action core pattern

Validators = Hash(default_value=0)

"""
    Validators:<address>:active: bool
        - If the validator can be included in the active set. False if validator has left.
    
    Validators:<address>:locked: None or float 
        - The amount of tokens locked by the validator
    
    Validators:<address>:unbonding: Date or None
        - The date at which the validator can recover their locked validator tokens, False if they are not unbonding
    
    Validators:<address>:power: float
        - the voting power of the validator
    
    Validators:<address>:commission: float
        - the amount of commission that the validator takes from fees
    
    Validators:<address>:epoch_joined: int
        - The index of current_epoch + 1
    
    Validators:<address>:epoch_collected: int or None
        - The index of the last epoch which rewards were collected for.
"""

ValidatorsActive = Hash()  # Validators Active - A list of validators in the active set.

# StakingEpochs = Hash()  # Staking Epochs
Epoch_I = Variable()  # Epoch Index - The index tracking the current epoch : int
Delegators = Hash(default_value=0)  # Delegations:<delegator_account>:<validator_account> : float
TotalPower = Variable()  # Total Power - The total voting power among all validators : float

Rules = (
    Hash()
)  # This state is used to store the rules for the network. Alterable via governance votes.
"""
    {
        v_max: int, # The maximum number of validators in the active set.
        v_lock: float, # The fee that validators take from rewards.
        v_min_commission: float, # The minimum commission that validators can take.
        fee_dist: list, # The distribution of txn fees between validators, black_hole, contract creators, and dao. e.g. [0.5, 0.2, 0.2, 0.1]
        unbonding_period: int, # The days that validators must wait before they can recover their locked tokens.
        epoch_length: int, # The number of hours in an epoch.
        min_vote_turnout: float, # The minimum percentage of power that must vote on a proposal for it to be valid.
        min_vote_ratio: float, # The minimum percentage of validators that must vote yes for a proposal to be valid.
    }
"""

# Votes = Hash(
#     default_value=False
# )  # votes[] = {"y": bool, "n": bool, rule: str, arg: Any, "voters": list, "finalized": bool}
# Proposal_I = (
#     Variable()
# )  # The index of the current proposal - when a proposal is created, the index is incremented.


DEFAULT_RULES = {
    "v_max": 0,
    "v_lock": 0.0,
    "v_min_commission": 0.0,
    "fee_dist": [0.0, 0.0, 0.0, 0.0],
    "unbonding_period": 0,
    "epoch_length": 0,
    "min_vote_turnout": 0.0,
    "min_vote_ratio": 0.0,
}


@construct
def seed(genesis_nodes: list, rules: dict = {}):
    Rules["v_max"] = rules.get("v_max", DEFAULT_RULES["v_max"])
    Rules["v_lock"] = rules.get("v_lock", DEFAULT_RULES["v_lock"])
    Rules["v_min_commission"] = rules.get("v_min_commission", DEFAULT_RULES["v_min_commission"])
    Rules["fee_dist"] = rules.get("fee_dist", DEFAULT_RULES["fee_dist"])
    Rules["unbonding_period"] = rules.get("unbonding_period", DEFAULT_RULES["unbonding_period"])
    Rules["epoch_length"] = rules.get("epoch_length", DEFAULT_RULES["epoch_length"])
    
    Epoch_I.set(0)
    TotalPower.set(0)
    
    for node in genesis_nodes:
        Validators[node, 'active'] = True
        Validators[node, "locked"] = Rules["v_lock"]
        Validators[node, "unbonding"] = None
        Validators[node, "power"] = Rules["v_lock"]
        Validators[node, "commission"] = Rules["v_min_commission"]
        Validators[node, "epoch_joined"] = 0
        Validators[node, "epoch_collected"] = None
        Validators[node, "is_genesis_node"] = True # Not returned tokens on leave.
        TotalPower.set(TotalPower.get() + Rules["v_lock"])


@export
def join(commission: float):
    assert not Validators[ctx.caller, 'active'], "Already a validator"
    
    join_fee = Rules["v_lock"]

    assert currency.balance_of(ctx.caller) >= join_fee, "Insufficient funds to join"
    min_commission = Rules["v_min_commission"]

    assert commission >= min_commission, f"Commission must be at least {min_commission}"

    currency.transfer_from(amount=join_fee, to=ctx.this, main_account=ctx.caller)

    Validators[ctx.caller, 'active'] = True
    Validators[ctx.caller, "locked"] = join_fee
    Validators[ctx.caller, "unbonding"] = None
    Validators[ctx.caller, "power"] += join_fee
    Validators[ctx.caller, "commission"] = commission
    Validators[ctx.caller, "epoch_joined"] = Epoch_I.get() + 1
    Validators[ctx.caller, "epoch_collected"] = None
    Validators[ctx.caller, "is_genesis_node"] = None
    
    TotalPower.set(TotalPower.get() + join_fee)


@export
def announce_validator_leave():
    assert Validators[ctx.caller, 'active'], "Not a validator"
    assert not Validators[ctx.caller, "unbonding"], "Already unbonding"

    Validators[ctx.caller, "unbonding"] = now + datetime.timedelta(
        days=Rules["unbonding_period"]
    )


@export
def cancel_validator_leave():
    assert Validators[ctx.caller, 'active'], "Not an active validator"
    assert Validators[ctx.caller, "unbonding"], "Not unbonding"

    Validators[ctx.caller, "unbonding"] = None


@export
def validator_leave():
    assert Validators[ctx.caller, 'active'], "Not a validator"
    assert Validators[ctx.caller, "unbonding"], "Not unbonding"
    assert Validators[ctx.caller, "unbonding"] <= now, "Unbonding period not over"

    # perform the transfer
    if not Validators[ctx.caller, "is_genesis_node"]:
        currency.transfer(Validators[ctx.caller, "locked"], ctx.caller)
        
    # reset the validator record.
    Validators[ctx.caller, 'active'] = False
    Validators[ctx.caller, "unbonding"] = None
    Validators[ctx.caller, "power"] -= Validators[ctx.caller, "locked"]
    Validators[ctx.caller, "locked"] = None
    Validators[ctx.caller, "is_genesis_node"] = None
    
    TotalPower.set(TotalPower.get() - Validators[ctx.caller, "locked"])


@export
def delegate(validator: str, amount: float):
    """
    Called by : Delegator
    * Delegates tokens to a validator.
    * Increases the voting power of the validator.
    * Cannot delegate to a validator that is unbonding.
    * Cannot delegate to a validator if caller has a delegation to validator that is unbonding.
    * Value must be greater than 0.
    """
    assert amount > 0, "Amount must be greater than 0"
    assert Validators[validator, 'active'], "Validator is not registered"
    assert not Validators[validator, "unbonding"], "Validator is unbonding"
    assert not Delegators[ctx.caller, validator, "unbonding"], "This delegation is unbonding, please cancel the unbonding period first"
    
    currency_balances = ForeignHash(foreign_contract="currency", foreign_name="balances")
    assert currency_balances[ctx.caller] >= amount, "Insufficient funds"
    assert currency_balances[ctx.caller, ctx.this] >= amount, "Insufficient allowance"

    currency.transfer_from(amount=amount, to=ctx.this, main_account=ctx.caller)

    Delegators[ctx.caller, validator, "amount"] += amount
    Delegators[ctx.caller, validator, "epoch_joined"] = Epoch_I.get() + 1
    Validators[validator, "power"] += amount
    
    TotalPower.set(TotalPower.get() + amount)


@export
def announce_delegator_leave(validator: str):
    """
    Called by : Delegator
    * Immediately removes delegated voting power from a validator.
    * If the validator is unbonding, the delegated tokens are locked until the validator unbonding period is over.
    * If the validator is not unbonding, the delegated tokens can be claimed after the standard unbonding period, defined in Rules.
    * If the validator is no longer registered, the delegated tokens can be claimed immediately / unbonding period set to now.
    """
    assert Delegators[ctx.caller, validator, "amount"] > 0, "No delegation to leave"
    assert not Delegators[ctx.caller, validator, "unbonding"], "Already unbonding"

    # Validator has left the network
    if not Validators[validator, 'active']:
        currency.transfer(Delegators[ctx.caller, validator, "amount"], ctx.caller)
        Validators[validator, "power"] -= Delegators[ctx.caller, validator, "amount"]
        Delegators[ctx.caller, validator, "amount"] = 0
        return

    # Validator is unbonding
    if Validators[validator, "unbonding"]:
        Delegators[ctx.caller, validator, "unbonding"] = Validators[validator, "unbonding"]
        Validators[validator, "power"] -= Delegators[ctx.caller, validator, "amount"]
        return

    # Validator is not unbonding
    Delegators[ctx.caller, validator, "unbonding"] = now + datetime.timedelta(days=Rules["unbonding_period"])
    Validators[validator, "power"] -= Delegators[ctx.caller, validator, "amount"]


@export
def cancel_delegator_leave(validator: str):
    """
    Called by : Delegator
    * Cancels the unbonding period for a delegation.
    """
    assert Delegators[ctx.caller, validator, 'amount'] > 0, "No delegation to leave"
    assert Delegators[ctx.caller, validator, "unbonding"], "Not unbonding"

    Delegators[ctx.caller, validator, "unbonding"] = None
    Validators[validator, "power"] += Delegators[ctx.caller, validator, "amount"]
    

@export
def redelegate(from_validator: str, to_validator: str, amount: float):
    """
    Called by : Delegator
    * Moves tokens delegated from one validator to another.
    * Can be performed when there is a delegation to the from_validator.
    * Can be performed when the to_validator is not unbonding and is active.
    * Cannot be performed when the delegator is unbonding from the validator.
    * Cannot be performed when the delegator is unbonding from the to_validator.
    """
    # Validator Checks
    assert Validators[to_validator, 'active'], "To validator is not active"
    assert not Validators[to_validator, "unbonding"], "To validator is unbonding"
    
    # Delegator Checks
    assert Delegators[ctx.caller, from_validator, 'amount'] > 0, "No delegation to move"
    assert Delegators[ctx.caller, from_validator, 'amount'] >= amount, "Insufficient delegation"
    assert not Delegators[ctx.caller, from_validator, "unbonding"], "The 'from' delegation is unbonding, cancel the unbonding first"
    assert not Delegators[ctx.caller, to_validator, "unbonding"], "The 'to' delegation is unbonding, cancel the unbonding first"

    Delegators[ctx.caller, from_validator, "amount"] -= amount
    Delegators[ctx.caller, to_validator, "amount"] += amount
    Validators[from_validator, "power"] -= amount
    Validators[to_validator, "power"] += amount
    
    
@export
def delegator_leave(validator: str):
    """
    Called by : Delegator
    * Can be called after the unbonding period
    """
    assert Delegators[ctx.caller, validator, 'amount'] > 0, "No delegation to leave"
    assert Delegators[ctx.caller, validator, "unbonding"], 'Not unbonding, call announce_delegator_leave first'
    assert Delegators[ctx.caller, validator, "unbonding"] <= now, 'Unbonding period not over'
    
    currency.transfer(Delegators[ctx.caller, validator, "amount"], ctx.caller)
    
    Delegators[ctx.caller, validator, "amount"] = 0
    Delegators[ctx.caller, validator, "unbonding"] = None
    Delegators[ctx.caller, validator, "validator"] = None


# @export
# def propose(type_of_vote: str, arg: Any):
#     assert ctx.caller in VA.get(), "Only nodes can propose new votes"


#     assert type_of_vote in types.get(), "Invalid type"
#     proposal_id = Proposal_I.get() + 1
#     Proposal_I.set(proposal_id)
#     votes[proposal_id][] = {"yes": 1, "no": 0, "type": type_of_vote, "arg": arg, "voters": [ctx.caller], "finalized": False}
#     total_votes.set(proposal_id)

#     if len(votes[proposal_id]["voters"]) >= len(nodes.get()) // 2: # Single node network edge case
#         if not votes[proposal_id]["finalized"]:
#             finalize_vote(proposal_id)

#     return proposal_id

# @export
# def vote(proposal_id: int, vote: str):
#     assert ctx.caller in nodes.get(), "Only nodes can vote"
#     assert votes[proposal_id], "Invalid proposal"
#     assert votes[proposal_id]["finalized"] == False, "Proposal already finalized"
#     assert vote in ["Y", "N"], "Invalid vote"
#     assert ctx.caller not in votes[proposal_id]["voters"], "Already voted"

#     # Do this because we can't modify a dict in a hash without reassigning it
#     cur_vote = votes[proposal_id]
#     cur_vote[vote] += 1
#     cur_vote["voters"].append(ctx.caller)
#     votes[proposal_id] = cur_vote

#     if len(votes[proposal_id]["voters"]) >= len(nodes.get()) // 2:
#         if not votes[proposal_id]["finalized"]:
#             finalize_vote(proposal_id)

#     return cur_vote


# def finalize_vote(proposal_id: int):
#     cur_vote = votes[proposal_id]

#     # Check if majority yes
#     if cur_vote["yes"] > cur_vote["no"]:
#         if cur_vote["type"] == "add_member":
#             nodes.set(nodes.get() + [cur_vote["arg"]])
#         elif cur_vote["type"] == "remove_member":
#             nodes.set([node for node in nodes.get() if node != cur_vote["arg"]])
#             force_leave(cur_vote["arg"])
#         elif cur_vote["type"] == "reward_change":
#             rewards.set_value(new_value=cur_vote["arg"])
#         elif cur_vote["type"] == "dao_payout":
#             dao.transfer_from_dao(args=cur_vote["arg"])
#         elif cur_vote["type"] == "stamp_cost_change":
#             stamp_cost.set_value(new_value=cur_vote["arg"])
#         elif cur_vote["type"] == "change_registration_fee":
#             registration_fee.set(cur_vote["arg"])
#         elif cur_vote["type"] == "change_types":
#             types.set(cur_vote["arg"])

#     cur_vote["finalized"] = True

#     votes[proposal_id] = cur_vote
#     return cur_vote

# def force_leave(node: str):
#     pending_leave[node] = now + datetime.timedelta(days=7)

# @export
# def announce_leave():
#     assert ctx.caller in nodes.get(), "Not a node"
#     assert pending_leave[ctx.caller] == False, "Already pending leave"
#     pending_leave[ctx.caller] = now + datetime.timedelta(days=7)

# @export
# def slash

# @export
# def leave():
#     assert pending_leave[ctx.caller] < now, "Leave announcement period not over"
#     if ctx.caller in nodes.get():
#         nodes.set([node for node in nodes.get() if node != ctx.caller])
#     pending_leave[ctx.caller] = False

# # @export
# # def register():
# #     assert ctx.caller not in nodes.get(), "Already a node"
# #     assert pending_registrations[ctx.caller] == False, "Already pending registration"
# #     currency.transfer_from(amount=registration_fee.get(), to=ctx.this, main_account=ctx.caller)
# #     holdings[ctx.caller] = registration_fee.get()
# #     pending_registrations[ctx.caller] = True

# # @export
# # def unregister():
# #     assert ctx.caller not in nodes.get(), "If you're a node already, you can't unregister. You need to leave or be removed."
# #     assert pending_registrations[ctx.caller] == True, "No pending registration"
# #     if holdings[ctx.caller] > 0:
# #         currency.transfer(holdings[ctx.caller], ctx.caller)
# #     pending_registrations[ctx.caller] = False
# #     holdings[ctx.caller] = 0
