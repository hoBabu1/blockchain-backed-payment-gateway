//SPDX-License-Identifier:MIT

pragma solidity 0.8.20;

import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Pausable} from "openzeppelin-contracts/contracts/utils/Pausable.sol";

contract OnChainPaymentGateWay is Ownable, Pausable {
    using SafeERC20 for IERC20;

    IERC20 public immutable acceptedToken;

    event MerchantRegistered(
        address indexed merchant,
        uint256 indexed registeredAT,
        string businessName
    );
    event PaymentIntentCreated(
        address merchant,
        address coustmer,
        uint256 amount,
        uint256 createdAt
    );

    event Paid(uint256 indexed amount, uint256 paidAt);
    error MerchantNotRegistered();
    error InvalidAmount(uint256 actualAmount, uint256 currAmount);
    error TimePassed();
    error OnlyCustomerCanPay();

    struct Merchant {
        address merchant;
        string businessName;
        uint256 registeredAt;
    }

    struct PaymentIntent {
        address merchant;
        address customer;
        uint256 amount;
        uint256 createdAt;
        uint256 expiryTime;
        uint256 confirmedAt;
        bool isPaid;
        string description;
    }

    uint256 paymentId = 0;

    mapping(address addressOfMerchant => Merchant merchant) public merchantInfo;
    // mapping(address _merchant => mapping(uint256 _payId => PaymentIntent))
    //     public paymentIntentInfo;

    mapping(uint256 _payId => PaymentIntent) public paymentIntentInfo;

    modifier onlyMerchant() {
        if (merchantInfo[msg.sender].merchant == address(0)) {
            revert MerchantNotRegistered();
        }
        _;
    }

    constructor(address _paymentToken) Ownable(msg.sender) {
        acceptedToken = IERC20(_paymentToken);
    }

    function registerMerchant(string memory _businessName) external whenNotPaused {
        merchantInfo[msg.sender] = Merchant({
            merchant: msg.sender,
            businessName: _businessName,
            registeredAt: block.timestamp
        });

        emit MerchantRegistered(msg.sender, block.timestamp, _businessName);
    }

    function createPaymentIntent(
        uint256 _amount,
        address _coustmer,
        uint256 _expiryDuration,
        string memory _shortDescription
    ) external onlyMerchant whenNotPaused {
        uint256 currPayId = ++paymentId;
        paymentIntentInfo[currPayId] = PaymentIntent({
            merchant: msg.sender,
            customer: _coustmer,
            amount: _amount,
            createdAt: block.timestamp,
            expiryTime: block.timestamp + _expiryDuration,
            confirmedAt: 0,
            isPaid: false,
            description: _shortDescription
        });

        emit PaymentIntentCreated(
            msg.sender,
            _coustmer,
            _amount,
            block.timestamp
        );
    }

    function executePayment(uint256 _payId, uint256 _amount) external whenNotPaused {
        PaymentIntent memory _info = paymentIntentInfo[_payId];

        if (_amount != _info.amount) {
            revert InvalidAmount(_info.amount, _amount);
        }

        if (block.timestamp > _info.expiryTime) {
            revert TimePassed();
        }

        if (msg.sender != _info.customer) {
            revert OnlyCustomerCanPay();
        }

        acceptedToken.safeTransferFrom(msg.sender, _info.merchant, _amount);

        paymentIntentInfo[_payId].isPaid = true;
        paymentIntentInfo[_payId].confirmedAt = block.timestamp;

        emit Paid(_amount, block.timestamp);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }
}
