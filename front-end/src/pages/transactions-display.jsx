import { useState, useEffect } from "react";
import { Center, Stack, Heading, Card} from "@chakra-ui/react";

export default function TransactionsDisplay() {
    const [transactions, setTransactions] = useState([]);

    useEffect(() => {
        fetch("http://127.0.0.1:8000/report-expense/", {
            method: "get"
        })
            .then(Response => Response.json())
            .then(data => setTransactions(data.data))

            .catch(error => console.error("Failed to get transactions", error))
    }, []);

    return(
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="center"
            >
                <Heading>
                    Transactions list
                </Heading>

                {transactions?.map((item) => (
                    <Card.Root size="sm" width={"35vh"}>
                      <Card.Header>
                        <Heading size="md"> {item.value} - {item.category}</Heading>
                      </Card.Header>
                      <Card.Body color="fg.muted">
                        {item.label}
                      </Card.Body>
                    </Card.Root>
                ))}

            </Stack>
        </Center>
    )
}