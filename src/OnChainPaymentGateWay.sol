//SPDX-License-Identifier:MIT

pragma solidity 0.8.20;

import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Pausable} from "openzeppelin-contracts/contracts/utils/Pausable.sol";

/**
 * Note - Lets say that 3 Coin is enabled of now - TokenA, TokenB and TokenC. Merchant created a intent with TokenA but before payment of that intent
 * TokenA disabled. Then Customer cannot pay for that intent.
 * Two ways
 * - create a new intent
 * - modify the intent
 */

contract OnChainPaymentGateWay is Ownable, Pausable {
    using SafeERC20 for IERC20;

    event MerchantRegistered(
        address indexed merchant,
        uint256 indexed registeredAt,
        string businessName
    );
    event PaymentIntentCreated(
        uint256 indexed payId,
        address indexed customer,
        uint256 indexed amount,
        address merchant,
        uint256 createdAt,
        uint256 expiryTime
    );

    event TokenEnabled(address indexed _token);
    event TokenDisabled(address indexed _token);

    event Paid(
        uint256 indexed payId,
        uint256 indexed amount,
        uint256 indexed paidAt
    );
    event IntentUpdated(
        uint256 indexed payId,
        address indexed customer,
        uint256 indexed amount,
        address token,
        uint256 updatedAt
    );
    error MerchantNotRegistered();
    error InvalidAmount(uint256 actualAmount, uint256 currAmount);
    error TimePassed();
    error OnlyCustomerCanPay();
    error InvalidToken();
    // error NotEnabled();
    error AlreadyPaid();
    error InvalidTokenOrNotEnabled();
    error MerchantIsInactive();

    struct Merchant {
        string businessName;
        uint256 registeredAt;
        bool isActive;
    }

    struct PaymentIntent {
        address merchant;
        address customer;
        uint256 amount;
        uint256 createdAt;
        IERC20 token;
        uint256 expiryTime;
        uint256 paidAt;
        bool isPaid;
        uint256 lastUpdatedAt;
    }

    uint256 paymentId = 0;

    mapping(address addressOfMerchant => Merchant merchant) public merchantInfo;
    // mapping(address _merchant => mapping(uint256 _payId => PaymentIntent))
    //     public paymentIntentInfo;

    mapping(uint256 _payId => PaymentIntent) public paymentIntentInfo;
    mapping(IERC20 _token => bool _isTokenEnabled) public isTokenEnabled;
    modifier onlyMerchant() {
        if (merchantInfo[msg.sender].registeredAt == 0) {
            revert MerchantNotRegistered();
        }
        _;
    }

    modifier checkTokenEnabled(IERC20 _token) {
        if (!isTokenEnabled[_token]) {
            revert InvalidTokenOrNotEnabled();
        }
        _;
    }

    modifier isMerchantActive(address _merchant) {
        if (!merchantInfo[_merchant].isActive) {
            revert MerchantIsInactive();
        }
        _;
    }

    constructor(address _owner) Ownable(_owner) {}

    // ================================================================
    // │                   onlyMerchant                                │
    // ================================================================

    function registerMerchant(
        string memory _businessName
    ) external whenNotPaused {
        merchantInfo[msg.sender] = Merchant({
            businessName: _businessName,
            registeredAt: block.timestamp,
            isActive: true
        });

        emit MerchantRegistered(msg.sender, block.timestamp, _businessName);
    }

    function createPaymentIntent(
        uint256 _amount,
        address _customer,
        uint256 _expiryDuration,
        IERC20 _tokenAddress
    )
        external
        onlyMerchant
        whenNotPaused
        checkTokenEnabled(_tokenAddress)
        isMerchantActive(msg.sender)
    {
        uint256 currPayId = ++paymentId;
        paymentIntentInfo[currPayId] = PaymentIntent({
            merchant: msg.sender,
            customer: _customer,
            amount: _amount,
            createdAt: block.timestamp,
            token: _tokenAddress,
            expiryTime: block.timestamp + _expiryDuration,
            paidAt: 0,
            isPaid: false,
            lastUpdatedAt: block.timestamp
        });

        emit PaymentIntentCreated(
            currPayId,
            _customer,
            _amount,
            msg.sender,
            block.timestamp,
            block.timestamp + _expiryDuration
        );
    }

    function updateIntent(
        uint256 _payId,
        uint256 _amount,
        IERC20 _token,
        address _customer
    )
        external
        whenNotPaused
        onlyMerchant
        checkTokenEnabled(_token)
        isMerchantActive(msg.sender)
    {
        PaymentIntent storage _info = paymentIntentInfo[_payId];
        if (_info.isPaid) {
            revert AlreadyPaid();
        }

        if (block.timestamp > _info.expiryTime) {
            revert TimePassed();
        }

        _info.amount = _amount;
        _info.token = _token;
        _info.customer = _customer;
        _info.lastUpdatedAt = block.timestamp;

        emit IntentUpdated(
            _payId,
            _customer,
            _amount,
            address(_token),
            block.timestamp
        );
    }

    // ================================================================
    // │                  Customer Interaction                         │
    // ================================================================

    function executePayment(
        uint256 _payId,
        uint256 _amount,
        IERC20 _token
    ) external whenNotPaused {
        PaymentIntent memory _info = paymentIntentInfo[_payId];

        if (!merchantInfo[_info.merchant].isActive) {
            revert MerchantIsInactive();
        }

        if (_info.isPaid == true) {
            revert AlreadyPaid();
        }

        if (_info.token != _token || !isTokenEnabled[_token]) {
            revert InvalidTokenOrNotEnabled();
        }

        if (_amount != _info.amount) {
            revert InvalidAmount(_info.amount, _amount);
        }

        if (block.timestamp > _info.expiryTime) {
            revert TimePassed();
        }

        if (msg.sender != _info.customer) {
            revert OnlyCustomerCanPay();
        }

        _info.token.safeTransferFrom(msg.sender, _info.merchant, _amount);

        paymentIntentInfo[_payId].isPaid = true;
        paymentIntentInfo[_payId].paidAt = block.timestamp;

        emit Paid(_payId, _amount, block.timestamp);
    }

    // ================================================================
    // │                        onlyOwner                              │
    // ================================================================

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    function enableToken(IERC20 _token) external onlyOwner {
        isTokenEnabled[_token] = true;
        emit TokenEnabled(address(_token));
    }

    function disableToken(
        IERC20 _token
    ) external onlyOwner checkTokenEnabled(IERC20(_token)) {
        isTokenEnabled[_token] = false;
        emit TokenDisabled(address(_token));
    }

    function makeMerchantInActive(address _merchant) external onlyOwner {
        merchantInfo[_merchant].isActive = false;
    }

    function emergencyWithdraw(address _token) external onlyOwner {
        IERC20(_token).safeTransfer(
            msg.sender,
            IERC20(_token).balanceOf(address(this))
        );
    }

    // ================================================================
    // │                  Getters                                     │
    // ================================================================

    function getMerchantInfo(
        address _merchant
    ) external view returns (Merchant memory) {
        return merchantInfo[_merchant];
    }

    function getPaymentIntentInfo(
        uint256 _payId
    ) external view returns (PaymentIntent memory) {
        return paymentIntentInfo[_payId];
    }

    function isTokenAllowed(IERC20 _token) external view returns (bool) {
        return isTokenEnabled[_token];
    }
}
