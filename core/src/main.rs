use rusqlite::{Connection, params};
use serde::{Deserialize, Serialize};
use std::io::{self, BufRead};

#[derive(Debug, Serialize, Deserialize, Clone)]
enum State {
    Idle,
    Researching,
    Specifying,
    CodingReady,
    Coding,
    QaRunning,
    Reviewing,
    AwaitApproval,
    Done,
}

#[derive(Debug, Deserialize)]
struct Request {
    method: String,
    params: Params,
}

#[derive(Debug, Deserialize)]
struct Params {
    feature: String,
}

#[derive(Debug, Serialize)]
struct Response {
    result: String,
}

fn init_db(conn: &Connection) {
    conn.execute(
        "CREATE TABLE IF NOT EXISTS features (
            feature TEXT PRIMARY KEY,
            state TEXT NOT NULL
        )",
        [],
    ).unwrap();
}

fn get_state(conn: &Connection, feature: &str) -> State {
    let mut stmt = conn.prepare(
        "SELECT state FROM features WHERE feature = ?1"
    ).unwrap();

    let result: Result<String, _> = stmt.query_row(
        params![feature],
        |row| row.get(0)
    );

    match result {
        Ok(s) => serde_json::from_str(&format!("\"{}\"", s)).unwrap(),
        Err(_) => State::Idle,
    }
}

fn set_state(conn: &Connection, feature: &str, state: &State) {
    conn.execute(
        "INSERT OR REPLACE INTO features (feature, state) VALUES (?1, ?2)",
        params![feature, format!("{:?}", state)],
    ).unwrap();
}

fn handle(req: Request, conn: &Connection) -> Response {
    let feature = req.params.feature;
    let state = get_state(conn, &feature);

    let result = match req.method.as_str() {
        "research" => {
            set_state(conn, &feature, &State::Researching);
            set_state(conn, &feature, &State::AwaitApproval);
            "Research requested".to_string()
        }

        "spec" => {
            set_state(conn, &feature, &State::Specifying);
            set_state(conn, &feature, &State::AwaitApproval);
            "Spec requested".to_string()
        }

        "full" => match state {
            State::Idle => {
                set_state(conn, &feature, &State::Researching);
                set_state(conn, &feature, &State::AwaitApproval);
                "Auto: research started".to_string()
            }
            State::CodingReady => "Waiting for human coding".to_string(),
            State::Coding => {
                set_state(conn, &feature, &State::QaRunning);
                set_state(conn, &feature, &State::AwaitApproval);
                "QA + review triggered".to_string()
            }
            _ => format!("No action for state {:?}", state),
        },

        "approve" => {
            let next = match state {
                State::AwaitApproval => Some(State::CodingReady),
                State::QaRunning => Some(State::Reviewing),
                State::Reviewing => Some(State::Done),
                _ => None,
            };

            match next {
                Some(s) => {
                    set_state(conn, &feature, &s);
                    format!("[APPROVED] → {:?}", s)
                }
                None => format!("Cannot approve from {:?}", state),
            }
        }

        "reject" => {
            set_state(conn, &feature, &State::Idle);
            "[REJECTED] reset to Idle".to_string()
        }

        _ => "Unknown method".to_string(),
    };

    Response { result }
}

fn main() {
    let conn = Connection::open("mcp.db").unwrap();
    init_db(&conn);

    let stdin = io::stdin();
    for line in stdin.lock().lines() {
        let line = line.unwrap();
        if line.trim().is_empty() {
            continue;
        }

        let req: Request = serde_json::from_str(&line).unwrap();
        let res = handle(req, &conn);

        println!("{}", serde_json::to_string(&res).unwrap());
    }
}
