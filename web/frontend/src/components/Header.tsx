import React from "react";

interface HeaderProps {
  workspaceName: string;
  userName: string;
  notionUrl: string;
}

const Header: React.FC<HeaderProps> = ({ workspaceName, userName, notionUrl }) => {
  return (
    <div className="hdr">
      <a className="hdr-logo" href="#">
        Notion Pilot
      </a>
      <span className="hdr-badge">COCKPIT</span>

      <span id="hdr-ws" className="hdr-ws">
        {workspaceName}
      </span>

      <span className="hdr-user">{userName}</span>

      <a
        className="hdr-notion-link"
        href={notionUrl || "https://notion.so"}
        target="_blank"
        rel="noopener noreferrer"
      >
        Open in Notion ↗
      </a>

      <a className="hdr-logout" href="/auth/logout">
        Sign out
      </a>
    </div>
  );
};

export default Header;
