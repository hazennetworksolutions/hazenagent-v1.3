// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract HazenAgent {
    // ─── Agent Metadata ───────────────────────────────────────────────────────
    string  public constant NAME        = "HazenAgent";
    string  public constant DESCRIPTION = "Enterprise-Grade Crypto Intelligence AI";
    string  public constant VERSION     = "1.0.0";
    string  public agentUrl             = "https://hazenagent.xyz";
    address public owner;

    // ─── Inference Config ─────────────────────────────────────────────────────
    uint256 public queryFee     = 0.0001 ether;
    uint256 public requestCount;

    // ─── Structs ──────────────────────────────────────────────────────────────
    struct InferenceRequest {
        address requester;
        string  prompt;
        uint256 fee;
        uint256 timestamp;
        bool    fulfilled;
    }

    struct InferenceResult {
        bytes32 requestId;
        string  result;
        bytes32 proofHash;
        uint256 timestamp;
    }

    // ─── Storage ──────────────────────────────────────────────────────────────
    mapping(bytes32 => InferenceRequest) public requests;
    mapping(bytes32 => InferenceResult)  public results;
    bytes32[] public requestIds;

    // ─── Events ───────────────────────────────────────────────────────────────
    event AgentDeployed(address indexed owner, string agentUrl);
    event InferenceRequested(bytes32 indexed requestId, address indexed requester, string prompt, uint256 fee);
    event InferenceFulfilled(bytes32 indexed requestId, bytes32 proofHash, uint256 timestamp);
    event PaymentReceived(address indexed from, uint256 amount);
    event Withdrawn(address indexed owner, uint256 amount);
    event FeeUpdated(uint256 oldFee, uint256 newFee);
    event AgentUrlUpdated(string oldUrl, string newUrl);

    // ─── Modifiers ────────────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    // ─── Constructor ──────────────────────────────────────────────────────────
    constructor() {
        owner = msg.sender;
        emit AgentDeployed(msg.sender, agentUrl);
    }

    // ─── Core: Request Inference ──────────────────────────────────────────────
    function requestInference(string calldata prompt) external payable returns (bytes32 requestId) {
        require(msg.value >= queryFee, "Insufficient fee");
        require(bytes(prompt).length > 0, "Empty prompt");

        requestId = keccak256(
            abi.encodePacked(msg.sender, prompt, block.timestamp, requestCount)
        );

        requests[requestId] = InferenceRequest({
            requester:  msg.sender,
            prompt:     prompt,
            fee:        msg.value,
            timestamp:  block.timestamp,
            fulfilled:  false
        });

        requestIds.push(requestId);
        requestCount++;

        emit InferenceRequested(requestId, msg.sender, prompt, msg.value);
        emit PaymentReceived(msg.sender, msg.value);
    }

    // ─── Core: Submit Inference Result ────────────────────────────────────────
    function submitInference(
        bytes32 requestId,
        string calldata result,
        bytes32 proofHash
    ) external onlyOwner {
        require(requests[requestId].requester != address(0), "Request not found");
        require(!requests[requestId].fulfilled, "Already fulfilled");

        requests[requestId].fulfilled = true;

        results[requestId] = InferenceResult({
            requestId:  requestId,
            result:     result,
            proofHash:  proofHash,
            timestamp:  block.timestamp
        });

        emit InferenceFulfilled(requestId, proofHash, block.timestamp);
    }

    // ─── Read: Get Inference Result ───────────────────────────────────────────
    function getInferenceResult(bytes32 requestId) external view returns (
        string memory result,
        bytes32 proofHash,
        uint256 timestamp,
        bool fulfilled
    ) {
        return (
            results[requestId].result,
            results[requestId].proofHash,
            results[requestId].timestamp,
            requests[requestId].fulfilled
        );
    }

    // ─── Read: Get Agent Info ─────────────────────────────────────────────────
    function getAgentInfo() external view returns (
        string memory name,
        string memory agentUrl_,
        address owner_,
        uint256 totalRequests,
        uint256 balance,
        uint256 fee
    ) {
        return (NAME, agentUrl, owner, requestCount, address(this).balance, queryFee);
    }

    // ─── Read: Quote ──────────────────────────────────────────────────────────
    function quoteDispatch() external view returns (uint256) {
        return queryFee;
    }

    // ─── Owner: Withdraw ──────────────────────────────────────────────────────
    function withdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "Nothing to withdraw");
        (bool ok, ) = owner.call{value: balance}("");
        require(ok, "Transfer failed");
        emit Withdrawn(owner, balance);
    }

    // ─── Owner: Set Fee ───────────────────────────────────────────────────────
    function setQueryFee(uint256 newFee) external onlyOwner {
        emit FeeUpdated(queryFee, newFee);
        queryFee = newFee;
    }

    // ─── Owner: Set Agent URL ─────────────────────────────────────────────────
    function setAgentUrl(string calldata newUrl) external onlyOwner {
        emit AgentUrlUpdated(agentUrl, newUrl);
        agentUrl = newUrl;
    }

    // ─── Owner: Transfer Ownership ────────────────────────────────────────────
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Zero address");
        owner = newOwner;
    }

    receive() external payable {
        emit PaymentReceived(msg.sender, msg.value);
    }
}
