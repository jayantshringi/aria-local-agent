import React, { useState, useEffect } from "react";
import { X, Search, UserCheck, CheckCircle2, XCircle, Trash2, Plus, Sparkles, Clock } from "lucide-react";
import { api } from "../api";
import { MemorySearchResult, ProfileFact } from "../types";

interface MemoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialTab?: "about" | "search";
  onSelectSession?: (sessionId: string) => void;
}

export const MemoryModal: React.FC<MemoryModalProps> = ({
  isOpen,
  onClose,
  initialTab = "about",
  onSelectSession,
}) => {
  const [activeTab, setActiveTab] = useState<"about" | "search">(initialTab);

  // Facts state
  const [facts, setFacts] = useState<ProfileFact[]>([]);
  const [factsFilter, setFactsFilter] = useState<string>("all");
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [loadingFacts, setLoadingFacts] = useState(false);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<MemorySearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
      loadFacts();
    }
  }, [isOpen, initialTab]);

  const loadFacts = async () => {
    setLoadingFacts(true);
    try {
      const data = await api.listProfileFacts();
      setFacts(data);
    } catch (err) {
      console.error("Failed to load profile facts:", err);
    } finally {
      setLoadingFacts(false);
    }
  };

  const handleApprove = async (id: string) => {
    try {
      await api.updateProfileFact(id, "approved");
      await loadFacts();
    } catch (err) {
      console.error("Failed to approve fact:", err);
    }
  };

  const handleReject = async (id: string) => {
    try {
      await api.updateProfileFact(id, "rejected");
      await loadFacts();
    } catch (err) {
      console.error("Failed to reject fact:", err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteProfileFact(id);
      await loadFacts();
    } catch (err) {
      console.error("Failed to delete fact:", err);
    }
  };

  const handleAddFact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKey.trim() || !newValue.trim()) return;
    try {
      await api.createProfileFact(newKey.trim(), newValue.trim(), "approved");
      setNewKey("");
      setNewValue("");
      await loadFacts();
    } catch (err) {
      console.error("Failed to add fact:", err);
    }
  };

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const results = await api.searchMemory(searchQuery.trim(), 8);
      setSearchResults(results);
    } catch (err) {
      console.error("Memory search failed:", err);
    } finally {
      setSearching(false);
    }
  };

  if (!isOpen) return null;

  const filteredFacts = facts.filter((f) => {
    if (factsFilter === "all") return true;
    return f.status === factsFilter;
  });

  const pendingCount = facts.filter((f) => f.status === "pending").length;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card memory-modal" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div className="memory-tabs">
            <button
              className={`memory-tab-btn ${activeTab === "about" ? "active" : ""}`}
              onClick={() => setActiveTab("about")}
            >
              <UserCheck size={18} />
              <span>About Me (Profile Facts)</span>
              {pendingCount > 0 && <span className="tab-badge">{pendingCount}</span>}
            </button>
            <button
              className={`memory-tab-btn ${activeTab === "search" ? "active" : ""}`}
              onClick={() => setActiveTab("search")}
            >
              <Search size={18} />
              <span>Search Memory</span>
            </button>
          </div>
          <button className="btn-icon" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="memory-modal-body">
          {activeTab === "about" ? (
            <div className="about-me-tab">
              <div className="memory-section-desc">
                <Sparkles size={16} color="var(--primary)" />
                <span>
                  Aria automatically remembers facts about you and stores them locally in SQLite. Only <strong>Approved</strong> facts enter the AI prompt.
                </span>
              </div>

              {/* Add Fact Form */}
              <form className="add-fact-form" onSubmit={handleAddFact}>
                <input
                  type="text"
                  className="input-field"
                  placeholder="Fact Key (e.g., Preferred Language, Role)"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                />
                <input
                  type="text"
                  className="input-field"
                  placeholder="Value (e.g., Python & TypeScript, Senior Dev)"
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                />
                <button type="submit" className="btn btn-primary" style={{ whiteSpace: "nowrap" }}>
                  <Plus size={16} />
                  <span>Add Fact</span>
                </button>
              </form>

              {/* Status Filter Buttons */}
              <div className="facts-filter-bar">
                <button
                  className={`filter-chip ${factsFilter === "all" ? "active" : ""}`}
                  onClick={() => setFactsFilter("all")}
                >
                  All ({facts.length})
                </button>
                <button
                  className={`filter-chip ${factsFilter === "pending" ? "active" : ""}`}
                  onClick={() => setFactsFilter("pending")}
                >
                  Pending Review ({pendingCount})
                </button>
                <button
                  className={`filter-chip ${factsFilter === "approved" ? "active" : ""}`}
                  onClick={() => setFactsFilter("approved")}
                >
                  Approved ({facts.filter((f) => f.status === "approved").length})
                </button>
                <button
                  className={`filter-chip ${factsFilter === "rejected" ? "active" : ""}`}
                  onClick={() => setFactsFilter("rejected")}
                >
                  Rejected ({facts.filter((f) => f.status === "rejected").length})
                </button>
              </div>

              {/* Facts List */}
              <div className="facts-list">
                {loadingFacts ? (
                  <div className="empty-state">Loading facts...</div>
                ) : filteredFacts.length === 0 ? (
                  <div className="empty-state">No profile facts in this category.</div>
                ) : (
                  filteredFacts.map((fact) => (
                    <div key={fact.id} className="fact-item-card">
                      <div className="fact-item-content">
                        <div className="fact-item-header">
                          <span className="fact-key">{fact.key}</span>
                          <span className={`status-badge status-${fact.status}`}>
                            {fact.status === "approved"
                              ? "Approved (In Prompt)"
                              : fact.status === "pending"
                              ? "Pending Review"
                              : "Rejected"}
                          </span>
                        </div>
                        <div className="fact-value">{fact.value}</div>
                      </div>
                      <div className="fact-item-actions">
                        {fact.status !== "approved" && (
                          <button
                            className="btn btn-sm btn-approve"
                            title="Approve fact into prompt"
                            onClick={() => handleApprove(fact.id)}
                          >
                            <CheckCircle2 size={15} />
                            <span>Approve</span>
                          </button>
                        )}
                        {fact.status !== "rejected" && (
                          <button
                            className="btn btn-sm btn-reject"
                            title="Reject fact"
                            onClick={() => handleReject(fact.id)}
                          >
                            <XCircle size={15} />
                            <span>Reject</span>
                          </button>
                        )}
                        <button
                          className="btn-icon"
                          title="Delete permanently"
                          onClick={() => handleDelete(fact.id)}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            <div className="search-memory-tab">
              <form className="memory-search-form" onSubmit={handleSearch}>
                <div className="search-input-wrapper">
                  <Search size={18} className="search-icon" />
                  <input
                    type="text"
                    className="input-field search-input"
                    placeholder="Search past conversations, notes, decisions (e.g., 'What did we decide about X?')..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    autoFocus
                  />
                </div>
                <button type="submit" className="btn btn-primary" disabled={searching}>
                  {searching ? "Searching..." : "Search"}
                </button>
              </form>

              <div className="search-results-list">
                {searching ? (
                  <div className="empty-state">Searching vector and keyword index...</div>
                ) : searchResults.length === 0 ? (
                  <div className="empty-state">
                    {searchQuery ? "No matching memories found." : "Enter a search query to explore past memories."}
                  </div>
                ) : (
                  searchResults.map((result, idx) => (
                    <div
                      key={idx}
                      className="search-result-card"
                      onClick={() => {
                        if (result.source_type === "message" && onSelectSession) {
                          onClose();
                        }
                      }}
                    >
                      <div className="result-card-header">
                        <span className="source-tag">{result.source_type}</span>
                        {result.created_at && (
                          <span className="result-time">
                            <Clock size={12} style={{ marginRight: 4 }} />
                            {new Date(result.created_at).toLocaleString()}
                          </span>
                        )}
                        <span className="relevance-score">
                          RRF Score: {(result.score * 100).toFixed(1)}
                        </span>
                      </div>
                      <div className="result-text">{result.text}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
