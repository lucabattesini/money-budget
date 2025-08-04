import { useEffect, useState } from "react";
import { Center, Stack, Button, Heading, Input, Menu} from "@chakra-ui/react";

export default function ReportExpense() {
    const [amount, setAmount] = useState();
    const [description, setDescription] = useState("");
    const [categories, setCategories] = useState([]);
    const [selectedCategory, setSelectedCategory] = useState("Select category");

    useEffect(() => {
        fetch("http://127.0.0.1:8000/categories/", {
            method: "get"
        })
            .then(Response => Response.json())
            .then(data => setCategories(data.data))

            .catch(error => console.error("Failed to search categories", error))
    }, [])

    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="center"
            >
                <Heading>
                    Report Expense
                </Heading>

                <Input type="number" placeholder="Amount" variant="outline" />
                <Input placeholder="Description" variant="outline"/>

                <Menu.Root>
                    <Menu.Trigger asChild>
                        <Button variant="outline"> {selectedCategory} </Button>
                    </Menu.Trigger>
                    <Menu.Content>
                        {categories?.map((category) => (
                            <Menu.Item key={category.id} onClick={() => setSelectedCategory(category.name)}>
                                {category.name}
                            </Menu.Item>
                        ))}
                    </Menu.Content>
                </Menu.Root>
                
                <Button>Submit</Button>
            </Stack>
        </Center>
    );
}